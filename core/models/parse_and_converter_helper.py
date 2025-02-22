#处理anki笔记和各平台之间的笔记转换的问题
import re

VALID_LANGUAGES = {'python', 'javascript', 'java', 'c', 'c++', 'c#', 'html', 'css', 
                  'sql', 'typescript', 'php', 'ruby', 'go', 'swift', 'kotlin', 
                  'plain text'}  # 根据Notion API支持的语言列表精简

def parse_notion_https_for_database_id(url):
    """从 Notion 数据库链接中提取数据库 ID"""
    try:
        # 去除 URL 中的连字符和查询参数
        url_clean = url.replace('-', '').split('?', 1)[0]
        # 匹配 32 位十六进制的数据库 ID
        match = re.search(r'([0-9a-fA-F]{32})', url_clean)
        if match:
            database_id = match.group(1)
            # 格式化为带连字符的 UUID 形式
            database_id = f"{database_id[0:8]}-{database_id[8:12]}-{database_id[12:16]}-{database_id[16:20]}-{database_id[20:]}"
            return database_id
        else:
            return None
    except Exception as e:
        return None

class ToNotionConverter:

    def __init__(self) -> None:
        pass
    @staticmethod
    def convert_anki_html_to_notion_children(html_content: str):
        # 转换函数：将 Anki 笔记中的 HTML 正文转换为 Notion children 块
        import re
        from html import unescape
        
        # 处理代码块（提取语言参数）
        code_blocks = []
        def code_replacer(m):
            lang = m.group(1) or ''
            # 清理语言前缀（处理类似 language-python 的情况）
            lang = lang.replace('language-', '').lower()
            code = m.group(2)
            code_blocks.append({'lang': lang, 'content': unescape(code)})
            return f'__CODE_BLOCK_{len(code_blocks)-1}__'
        
        html_content = re.sub(
            r'<pre><code(?: class="([^"]*)")?>(.*?)</code></pre>',
            code_replacer, html_content, flags=re.DOTALL
        )
        
        # 处理内联格式
        replacements = [
            (r'<code>(.*?)</code>', r'`\1`'),
            (r'<strong>(.*?)</strong>', r'**\1**'),
            (r'<em>(.*?)</em>', r'_\1_'),
            (r'<del>(.*?)</del>', r'~~\1~~'),
            (r'<span[^>]*>(.*?)</span>', r'\1')
        ]
        for pattern, replacement in replacements:
            html_content = re.sub(pattern, replacement, html_content, flags=re.DOTALL)

        # 处理列表和段落
        html_content = re.sub(r'<ul>(.*?)</ul>', 
            lambda m: '\n'.join(f"- {x.group(1)}" for x in re.finditer(r'<li>(.*?)</li>', m.group(1), re.DOTALL)),
            html_content, flags=re.DOTALL)
        
        # 重建代码块结构
        children = []
        code_block_index = 0  # 添加独立的代码块索引计数器
        for part in re.split(r'__CODE_BLOCK_(\d+)__', html_content):
            if part.isdigit():
                index = int(part)
                if index < len(code_blocks):
                    # 使用单独的索引变量来避免与循环索引混淆
                    children.append({
                        "object": "block",
                        "type": "code",
                        "code": {
                            "rich_text": [{"type": "text", "text": {"content": code_blocks[index]['content']}}],
                            "language": code_blocks[index]['lang'] if code_blocks[index]['lang'] in VALID_LANGUAGES else "plain text"
                        }
                    })
                    code_block_index += 1  # 只有成功替换时才递增
                else:
                    # 没有更多代码块时保留原始文本
                    children.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"type": "text", "text": {"content": "【代码块解析错误】"}}]}
                    })
            elif part.strip():
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": part.strip()}}]}
                })
        
        return children
    pass