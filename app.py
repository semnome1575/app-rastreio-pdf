import os 
import io
import re
import zipfile
import pandas as pd
import qrcode
from fpdf2 import FPDF
# Forçando cache 2
from PIL import Image
from flask import Flask, render_template, request, send_file, redirect, url_for, abort

# --- CONFIGURAÇÕES GLOBAIS ---
# Permitir apenas estas extensões de arquivo
ALLOWED_EXTENSIONS = {'csv', 'xls', 'xlsx'} 
MAX_CONTENT_LENGTH = 16 * 1024 * 1024 # Limite de 16MB

# O Render lerá a variável de ambiente 'BASE_URL_RASTREAMENTO'.
BASE_URL_RASTREAMENTO = os.environ.get('BASE_URL_RASTREAMENTO', 'http://rastreio.exemplo.com.br/documento/')

app = Flask(__name__, template_folder='templates')
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH


# --- Funções de Segurança ---

def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Funções de Geração de PDF ---

def gerar_pdf_com_qr(dados_linha, base_url):
    """
    Gera um PDF contendo os dados de uma linha da planilha e um QR Code único.
    """
    # 1. Extração de Dados e Criação da URL Única
    # Assumimos que o primeiro item da linha é o ID_UNICO
    documento_id = str(dados_linha.iloc[0]) 
    url_rastreamento = f"{base_url}{documento_id}"
    
    # 2. Criação do QR Code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(url_rastreamento)
    qr.make(fit=True)
    
    img_qr = qr.make_image(fill_color="black", back_color="white")
    
    qr_buffer = io.BytesIO()
    img_qr.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    
    # 3. Criação do PDF (Usando fpdf2)
    pdf = FPDF('P', 'mm', 'A4')
    pdf.add_page()
    
    # --- Título ---
    pdf.set_font('Arial', 'B', 18)
    pdf.cell(0, 10, f'Documento: {documento_id}', 0, 1, 'C') 
    pdf.ln(10) 
    
    # --- Tabela de Dados ---
    pdf.set_font('Arial', 'B', 12)
    w_label = 75 
    w_value = 100
    
    # Itera sobre todas as colunas e valores
    for coluna, valor in zip(dados_linha.index, dados_linha.values):
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(w_label, 8, f'{coluna}:', 1, 0, 'L', 1) 
        pdf.set_fill_color(255, 255, 255)
        pdf.set_font('Arial', '', 12)
        
        display_value = str(valor) if pd.notna(valor) else "N/A"
        pdf.cell(w_value, 8, display_value, 1, 1, 'L', 1)
        pdf.set_font('Arial', 'B', 12)
            
    pdf.ln(15) 
    
    # --- Inserção do QR Code ---
    qr_code_size_mm = 40
    x_pos = (210 - qr_code_size_mm) / 2 
    
    pdf.set_font('Arial', '', 10)
    pdf.cell(0, 5, "Use a câmera do seu celular para rastrear:", 0, 1, 'C')
    pdf.ln(2)
    
    # Importante: O fpdf2 usa a biblioteca PIL (Pillow) para ler o buffer PNG
    pdf.image(qr_buffer, x=x_pos, y=pdf.get_y(), w=qr_code_size_mm, h=qr_code_size_mm, type='PNG')
    pdf.ln(qr_code_size_mm + 5) 

    # --- Nota de Rodapé ---
    pdf.set_font('Arial', 'I', 8)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 5, f'URL Única: {url_rastreamento}', 0, 1, 'C')

    # 4. Finalização
    pdf_buffer = io.BytesIO()
    # 'S' significa que o PDF deve ser retornado como uma string/bytes (buffer)
    pdf.output(pdf_buffer, 'S') 
    pdf_buffer.seek(0)
    
    return pdf_buffer


# --- ROTAS DO FLASK ---

@app.route('/', methods=['GET'])
def index():
    """Rota para a página inicial com o formulário de upload."""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """Rota para processar o upload do arquivo e gerar o ZIP."""
    if 'file' not in request.files:
        return "Nenhum arquivo enviado.", 400

    file = request.files['file']

    if file.filename == '':
        return "Nenhum arquivo selecionado.", 400

    if file and allowed_file(file.filename):
        try:
            # 1. Ler o arquivo para um buffer
            file_buffer = io.BytesIO(file.read())
            
            # 2. Ler os dados com Pandas (suporta CSV, XLS, XLSX)
            if file.filename.endswith('.csv'):
                df = pd.read_csv(file_buffer)
            else:
                # Tenta ler Excel (Requer openpyxl)
                df = pd.read_excel(file_buffer)

            # 3. Validação dos Dados
            if df.empty or df.columns[0] != 'ID_UNICO':
                return "O arquivo está vazio ou a primeira coluna não é 'ID_UNICO'. Certifique-se de que a primeira coluna tenha este nome.", 400
            
            # 4. Processamento para ZIP
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
                for index, row in df.iterrows():
                    # Gerar PDF para cada linha
                    pdf_data = gerar_pdf_com_qr(row, BASE_URL_RASTREAMENTO)
                    
                    # Nome do arquivo PDF no ZIP
                    documento_id = str(row.iloc[0])
                    pdf_filename = f"{documento_id}_rastreavel.pdf"
                    
                    # Adicionar o PDF ao ZIP
                    zip_file.writestr(pdf_filename, pdf_data.getvalue())

            zip_buffer.seek(0)
            
            # 5. Retornar o ZIP para o usuário
            return send_file(
                zip_buffer,
                mimetype='application/zip',
                as_attachment=True,
                download_name='documentos_rastreaveis.zip'
            )

        except Exception as e:
            app.logger.error(f"Erro no processamento do arquivo: {e}")
            return f"Erro interno ao processar o arquivo: {str(e)}", 500
    
    return "Tipo de arquivo não permitido (Use CSV, XLS ou XLSX).", 400


@app.route('/documento/<unique_id>')
def rastreamento(unique_id):
    """
    Rota para simular a página de rastreamento do documento.
    """
    if not re.match(r'^[a-zA-Z0-9\-\_]+$', unique_id):
        abort(404)
    
    return render_template('rastreamento.html', unique_id=unique_id)

@app.errorhandler(404)
def page_not_found(e):
    """Lida com erros 404 (Página não encontrada)."""
    return render_template('index.html', error="Página ou Documento não encontrado (Erro 404)."), 404


# O bloco abaixo é usado apenas para rodar o app localmente, o gunicorn no Render ignora isso
if __name__ == '__main__':
    # Cria uma pasta 'templates' se não existir para o render_template funcionar localmente
    if not os.path.exists('templates'):
        os.makedirs('templates')
    # Use o host '0.0.0.0' para garantir que o Flask funcione em qualquer ambiente
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))



