from flask import Flask, send_file
from fpdf2 import FPDF
import io

app = Flask(__name__)

@app.route('/')
def home():
    return "API PDF funcionando!"

@app.route('/gerar_pdf')
def gerar_pdf():
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="PDF gerado com fpdf2!", ln=True, align="C")
    
    # Criar buffer em memória para enviar o PDF
    pdf_buffer = io.BytesIO()
    pdf.output(pdf_buffer)
    pdf_buffer.seek(0)
    
    return send_file(pdf_buffer, as_attachment=True, download_name="teste.pdf", mimetype="application/pdf")

if __name__ == "__main__":
    app.run(debug=True)
