# 🏦 Conciliador Bancário

A very simple Streamlit web application to reconcile bank statement records with bookkeeping files.

I will not at any point apologize for mixing up English and Portuguese throughout the code or this README. It's entirely on purpose. I suggest you deal with it.

## 🚀 How to Run Locally

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the Streamlit app:
   ```bash
   streamlit run app.py
   ```

## 🌐 How to Run on the Web

1 (and only step). Just open the app right [here](https://conciliacaobancariabyvl.streamlit.app/)!

## 📄 How to Actually Use
1. Upload the **Contabilidade** and **Extrato Bancário** Excel files.
2. Select the value column from the Extrato file (automatically pre-selects `Valor` and other... suggestive words if present).

   2.1. You may review the uploaded data using the **Preview** dropdown.
3. Click **Run Reconciliation** to process the records.

   3.1. You may be asked to solve conflicts if more than a match is found. Don't be scared.
4. Stare at your screen to see the results.

   4.1. You may then download the unreconciled remainder sheets.
