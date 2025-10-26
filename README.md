# Q-A_Intelligence-agricultural_data-rainfall_data

An intelligent Question-Answering system built using Python and Flask that analyzes Indian agricultural crop production and rainfall datasets to provide meaningful insights.  
This project merges multiple government datasets and allows users to ask natural language queries such as:
> "Which state had the highest crop production in 2015?"  
> "Compare rainfall and wheat production in Maharashtra."

---

## Features

- Query engine to answer natural-language questions about agricultural data  
- Data integration combining rainfall data with crop production statistics  
- Analytical comparisons such as identifying the highest-producing states or rainfall trends  
- Flask-based web interface for an interactive and easy-to-use experience  
- Machine learning support using Scikit-learn for query similarity and understanding  

---

## Tech Stack

| Component | Technology Used |
|------------|------------------|
| Backend | Python, Flask |
| Data Processing | Pandas, NumPy |
| Machine Learning | Scikit-learn |
| Frontend | HTML, CSS |
| Data Source | Government datasets (crop production and rainfall) |

---

## How It Works

1. **Data Preprocessing:**  
   Cleans and merges crop and rainfall datasets on common attributes (State, Year, etc.)

2. **Vectorization & Similarity:**  
   Converts user queries into vector form and compares them with dataset attributes using cosine similarity.

3. **Query Resolution:**  
   Extracts relevant data and generates human-readable answers.

4. **Flask Web Application:**  
   Provides a simple web interface where users can input queries and view intelligent responses.

---
