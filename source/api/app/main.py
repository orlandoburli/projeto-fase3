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