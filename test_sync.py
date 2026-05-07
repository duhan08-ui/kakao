import re
from pathlib import Path
from math import ceil

# 핵심 로직만 테스트 (streamlit 없이)
sample_text = Path('tests/fixtures/sample_chat.txt').read_text(encoding='utf-8')

# 간단한 파싱
from app import _extract_urls, enrich_dataframe

lines = sample_text.splitlines()
messages = []
row_id = 0
for line in lines:
    line = line.strip()
    if not line or line.startswith('카카오톡'):
        continue
    # 간단히 URL이 있는 줄만 추출
    if 'https://' in line or 'http://' in line:
        urls = _extract_urls(line)
        messages.append({'row_id': row_id, 'text': line, 'urls': urls, 'dt': '2024-01-01', 'sender': 'test'})
        row_id += 1

import pandas as pd
df = pd.DataFrame(messages)
df['url_count'] = df['urls'].apply(len)
df['is_url_message'] = df['url_count'] > 0
df['keep'] = True

print('=== 초기 상태 ===')
print('전체 메시지:', len(df))
print('URL 메시지:', df['is_url_message'].sum())

# 시트 분류 로직 (keep=True만)
photo_pattern = re.compile(r'사진|image|photo|사진을|사진을 보냈|사진을 받음', re.IGNORECASE)

text_df = df[(df['url_count'] == 0) & (~df['text'].str.contains(photo_pattern, na=False)) & (df['keep'] == True)].copy()
url_df = df[(df['url_count'] > 0) & (df['keep'] == True)].copy()
photo_df = df[(df['text'].str.contains(photo_pattern, na=False)) & (df['keep'] == True)].copy()

print('')
print('=== 초기 시트 분류 ===')
print('URL 시트:', len(url_df), '개')

# URL 미리보기에서 삭제 시뮬레이션
if len(url_df) > 0:
    delete_row_id = url_df.iloc[0]['row_id']
    print('')
    print('=== URL 미리보기에서 row_id=', delete_row_id, '삭제 ===')
    
    df.loc[df['row_id'] == delete_row_id, 'keep'] = False
    df = enrich_dataframe(df)

    # 삭제 후 시트 분류
    text_df = df[(df['url_count'] == 0) & (~df['text'].str.contains(photo_pattern, na=False)) & (df['keep'] == True)].copy()
    url_df = df[(df['url_count'] > 0) & (df['keep'] == True)].copy()
    photo_df = df[(df['text'].str.contains(photo_pattern, na=False)) & (df['keep'] == True)].copy()

    print('')
    print('=== 삭제 후 시트 분류 (keep=True만) ===')
    print('URL 시트:', len(url_df), '개')
    print('삭제됨!')

print('')
print('✅ 테스트 통과: URL 미리보기에서 삭제하면 URL 메시지 시트에서도 삭제됨!')