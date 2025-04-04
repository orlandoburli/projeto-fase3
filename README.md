# Modelo de predição de ataque cardíaco

## Overview

Este projeto é um **modelo de predição de ataque cardíaco**, desenvolvido para receber dados sobre pacientes, treinar um modelo preditivo e realizar previsões sobre o risco de ataque cardíaco com base nas informações fornecidas. 

Foi usado um modelo de classificação `RandomForestClassifier`, para tentar realizar as predições. Para os atributos não numéricos, usamos um `LabelEncoder` para transformação em dados numéricos e assim podermos executar o aprendizado. 

A seguir está uma visão geral detalhada do funcionamento do projeto.

## Modelo de dados

Foi usado uma fonte de dados da plataforma kaggle, [Heart Failure Prediction Dataset](https://www.kaggle.com/datasets/fedesoriano/heart-failure-prediction)

## API's e fluxos

O projeto conta com 2 endpoints:

* `collect-and-train`: Coleta dados atualizados da plataforma kaggle, treina com o algoritmo de classificação e salva o modelo treinado em um banco de dados postgres.
* `predict`: Realiza uma predição com o último modelo salvo no banco de dados baseado nos dados inputados.

## Executando o projeto

Para executar o projeto (limpando instâncias anteriores, se houver), executar na pasta `/infra`:

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
}' | jq
```

Saída:

```json
{
  "prediction": "NoHeartDisease",
  "probability": {
    "NoHeartDisease": 0.63,
    "HeartDisease": 0.37
  }
}
```