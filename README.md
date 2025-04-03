

Executando o projeto (limpando instâncias anteriores, se houver). Executar na pasta `/infra`

```shell
docker compose down && docker compose build && docker compose up -d
```

Baixando o modelo de dados, executar o treino e salvar modelo treinado no banco de dados:

```shell
curl -X POST http://localhost:8000/collect-and-train 
```

Testando o modelo/predict 

```shell
curl -X POST http://localhost:8000/predict \
-H "Content-Type: application/json" \
-d '{
  "Age": 55,
  "Sex": "Male",
  "ChestPainType": "ATA",
  "RestingBP": 140,
  "Cholesterol": 240,
  "FastingBS": 1,
  "RestingECG": "Normal",
  "MaxHR": 150,
  "ExerciseAngina": "No",
  "Oldpeak": 1.5,
  "ST_Slope": "Up"
}'
```