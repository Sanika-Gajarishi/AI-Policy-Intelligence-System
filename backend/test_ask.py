import sys, os
sys.path.append(os.path.abspath('.'))
from routes.query import ask_question, QueryRequest
import json

# Load policy metadata
with open(os.path.join('data', 'policies.json'), 'r', encoding='utf-8') as f:
    policies = json.load(f)

cases = [
    {
        'question': 'Summarize the selected policies',
        'files': [
            'Gujarat_Integreated Renewable Policy_2025.pdf',
            'Maharashtra_Mukhyamantri Saur Krushi Vahini Yojana_Solar_2023.pdf',
            'Maharashtra_Renewable Energy_2015.pdf'
        ]
    },
    {
        'question': 'What are the key provisions for solar incentives in the Maharashtra Renewable Energy Policy 2015?',
        'files': ['Maharashtra_Renewable Energy_2015.pdf']
    },
    {
        'question': 'What are the main objectives of the Mukhyamantri Saur Krushi Vahini Yojana (Solar) policy?',
        'files': ['Maharashtra_Mukhyamantri Saur Krushi Vahini Yojana_Solar_2023.pdf']
    }
]

for case in cases:
    selected = [p for p in policies if p['file'] in case['files']]
    req = QueryRequest(
        question=case['question'],
        selected_policies=[{'file': p['file'], 'state': p['state'], 'power_type': p['power_type'], 'year': p['year']} for p in selected]
    )
    print('\n=== CASE ===')
    print('Question:', case['question'])
    print('Selected:', case['files'])
    res = ask_question(req)
    print('Warning:', res.get('warning'))
    print('Sources count:', len(res.get('sources', [])))
    print('Answer preview:', (res.get('answer') or '')[:400])
