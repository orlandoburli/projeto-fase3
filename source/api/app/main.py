import io

import psycopg2
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import os
import kagglehub
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
import joblib

app = FastAPI()

POSTGRES_USERNAME = os.environ.get("POSTGRES_USERNAME")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT")
POSTGRES_DB = os.environ.get("POSTGRES_DB")

# PostgreSQL database connection string
DB_URL = f"postgresql://{POSTGRES_USERNAME}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"


class TrainingResponse(BaseModel):
    message: str
    model_id: int


class PredictionInput(BaseModel):
    Age: int
    Sex: str
    ChestPainType: str
    RestingBP: int
    Cholesterol: int
    FastingBS: int
    RestingECG: str
    MaxHR: int
    ExerciseAngina: str
    Oldpeak: float
    ST_Slope: str


@app.post("/collect-and-train", response_model=TrainingResponse)
async def collect_and_train():
    try:
        # ‘Download’ do conjunto de dados a partir do Kaggle
        csv_path = kagglehub.dataset_download(
            handle='fedesoriano/heart-failure-prediction',
        )

        # Verificar se `csv_path` é um diretório e encontrar o arquivo CSV
        import os
        if os.path.isdir(csv_path):
            # Procurar por um arquivo CSV na pasta
            files = os.listdir(csv_path)
            csv_file = next((f for f in files if f.endswith(".csv")), None)
            if csv_file:
                csv_path = os.path.join(csv_path, csv_file)
            else:
                raise FileNotFoundError("Nenhum arquivo CSV foi encontrado na pasta do conjunto de dados baixado.")

        # Load the dataset
        data = pd.read_csv(csv_path)

        # Pré-processamento: Codificar variáveis categóricas e colunas binárias
        categorical_columns = ["Sex", "ChestPainType", "RestingECG", "ExerciseAngina", "ST_Slope"]
        label_encoders = {}

        for col in categorical_columns:
            le = LabelEncoder()
            data[col] = le.fit_transform(data[col])
            label_encoders[col] = le

        # Separando features para treino
        X = data.drop("HeartDisease", axis=1)  # Features
        y = data["HeartDisease"]  # Target

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

        # Treinando o modelo
        model = RandomForestClassifier(random_state=42)
        model.fit(X_train, y_train)

        # Serialização do Modelo em formato binário
        buffer = io.BytesIO()
        joblib.dump(model, buffer)
        buffer.seek(0)

        # Salvando o modelo treinado
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()

        # Criando a tabela se não existir
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS trained_models (
                id SERIAL PRIMARY KEY,
                model_name TEXT NOT NULL,
                model_data BYTEA NOT NULL,
                description TEXT
            );
            """
        )

        # Insere o modelo serializado
        cursor.execute(
            """
            INSERT INTO trained_models (model_name, model_data, description)
            VALUES (%s, %s, %s)
            RETURNING id;
            """,
            ("HeartFailure_RandomForest", buffer.getvalue(), "Random Forest model for heart failure prediction"),
        )

        # Recupera o id do modelo
        model_id = cursor.fetchone()[0]

        # Commit das mudanças e fecha conexão
        conn.commit()
        cursor.close()
        conn.close()

        return TrainingResponse(
            message="Dataset processado e modelo treinado com sucesso.",
            model_id=model_id
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@app.post("/predict")
async def predict(input_data: PredictionInput):
    try:
        # Conectando ao banco e retornando o ultimo modelo treinado...
        conn = psycopg2.connect(DB_URL)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT model_data 
            FROM trained_models
            ORDER BY id DESC
            LIMIT 1;
            """
        )
        row = cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="No trained model found in the database.")

        # Carregando o modelo serializado
        model_binary = row[0]
        buffer = io.BytesIO(model_binary)
        model = joblib.load(buffer)

        cursor.close()
        conn.close()

        # Preparando input para predição
        categorical_columns = ["Sex", "ChestPainType", "RestingECG", "ExerciseAngina", "ST_Slope"]

        input_dict = input_data.dict()
        for col in categorical_columns:
            if col in input_dict:
                if col == "Sex":
                    input_dict[col] = 1 if input_dict[col].lower() == "male" else 0
                elif col == "ChestPainType":
                    input_dict[col] = {"TA": 0, "ATA": 1, "NAP": 2, "ASY": 3}.get(input_dict[col], -1)
                elif col == "RestingECG":
                    input_dict[col] = {"Normal": 0, "ST": 1, "LVH": 2}.get(input_dict[col], -1)
                elif col == "ExerciseAngina":
                    input_dict[col] = 1 if input_dict[col].lower() == "yes" else 0
                elif col == "ST_Slope":
                    input_dict[col] = {"Up": 0, "Flat": 1, "Down": 2}.get(input_dict[col], -1)

        input_df = pd.DataFrame([input_dict])

        # Preenchendo as colunas que não foram informadas...
        required_columns = model.feature_names_in_
        missing_columns = [col for col in required_columns if col not in input_df.columns]
        for col in missing_columns:
            input_df[col] = 0

        input_df = input_df[required_columns]

        # Predict
        prediction = model.predict(input_df)
        probability = model.predict_proba(input_df)

        result = {
            "prediction": "HeartDisease" if prediction[0] == 1 else "NoHeartDisease",
            "probability": {
                "NoHeartDisease": probability[0][0],
                "HeartDisease": probability[0][1],
            },
        }

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
