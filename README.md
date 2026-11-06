# Sistema Inteligente para Gestão de Adoções e Previsão de Atividades da AJAPRA

## Sobre o Projeto

Este projeto foi desenvolvido como trabalho de portfólio do curso de Engenharia de Software com o objetivo de modernizar os processos da ONG AJAPRA, organização voltada à proteção e bem-estar animal.

A proposta consiste na criação de uma plataforma web para gerenciamento de adoções e armazenamento digital de informações, complementada por um sistema de previsão de atividades baseado em Inteligência Artificial.

O sistema busca substituir registros físicos por uma solução digital organizada, segura e acessível, facilitando consultas, geração de relatórios e apoio à tomada de decisões.

---

## Objetivos

### Objetivo Geral

Melhorar a organização das informações da ONG AJAPRA e auxiliar no planejamento de atividades futuras por meio de análise de dados e inteligência artificial.

### Objetivos Específicos

- Analisar os registros atuais utilizados pela ONG;
- Desenvolver uma plataforma para armazenamento digital das adoções;
- Facilitar a consulta de informações por meio de filtros personalizados;
- Gerar relatórios administrativos;
- Levantar o histórico de atividades da ONG;
- Desenvolver um modelo de previsão de demanda utilizando IA;
- Auxiliar o planejamento estratégico da instituição.

---

## Problema

Atualmente, parte dos registros da ONG é armazenada fisicamente, gerando dificuldades como:

- Demora na busca de informações;
- Risco de perda de documentos;
- Dificuldade de organização dos dados;
- Ausência de ferramentas para previsão de demanda futura.

---

## Solução Proposta

O sistema oferecerá uma plataforma web centralizada contendo:

- Cadastro de animais;
- Cadastro de adotantes;
- Registro de adoções;
- Pesquisa avançada com filtros;
- Armazenamento digital de informações;
- Geração de relatórios;
- Sistema inteligente de previsão de atividades futuras.

---

## Arquitetura do Sistema

```text
+----------------------+
| Interface do Usuário |
+----------+-----------+
           |
           v
+----------------------+
|      Backend         |
+----------+-----------+
           |
           +----------------+
           |                |
           v                v
+----------------+   +------------------+
| Banco de Dados |   | Agente de IA     |
+----------------+   +------------------+
```

### Componentes

#### Frontend

Responsável pela interação com os usuários.

Funcionalidades:

- Formulários de cadastro;
- Consultas;
- Relatórios;
- Painéis administrativos.

#### Backend

Responsável por:

- Processamento das requisições;
- Validação dos dados;
- Comunicação com banco de dados;
- Execução do agente de previsão.

#### Banco de Dados

Armazena:

- Usuários;
- Animais;
- Adotantes;
- Adoções;
- Histórico de atividades.

#### Agente de Previsão

Utiliza dados históricos para estimar:

- Quantidade de atividades futuras;
- Períodos de maior demanda;
- Necessidade de recursos e voluntários.

---

## Tecnologias Utilizadas

### Frontend

- HTML
- CSS
- JavaScript

### Backend

- Python
- Flask

### Banco de Dados

- Firebase Firestore

### Inteligência Artificial

Possíveis abordagens:

- Regressão Linear
- Séries Temporais
- Machine Learning

---

## Funcionalidades

### Gestão de Adoções

- Cadastro de animais;
- Cadastro de adotantes;
- Registro de adoções;
- Consulta de registros.

### Pesquisa Inteligente

Filtros por:

- Nome;
- Cidade;
- Data;
- Animal;
- Adotante.

### Inteligência Artificial

- Análise histórica;
- Identificação de padrões;
- Previsão de volume de atividades futuras.

---

## Instituição Parceira

**AJAPRA**  
Associação voltada à proteção, acolhimento e adoção responsável de animais.
