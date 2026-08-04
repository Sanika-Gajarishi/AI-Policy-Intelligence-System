import sys, os
sys.path.append(os.path.abspath('.'))
from services.rag_pipeline import process_pdf

file_name = 'Gujarat_Integreated Renewable Policy_2025.pdf'
file_path = os.path.join('data', 'raw_pdfs', file_name)
print('Reindexing', file_path)
try:
    process_pdf(file_path, 'Gujarat', '2025', 'January', 'Integreated Renewable Policy')
    print('Reindex succeeded')
except Exception as e:
    print('Reindex error:', e)
