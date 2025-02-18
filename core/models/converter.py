#处理anki笔记和各平台之间的笔记转换的问题

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
        for part in re.split(r'__CODE_BLOCK_(\d+)__', html_content):
            if part.isdigit():
                index = int(part)
                children.append({
                    "object": "block",
                    "type": "code",
                    "code": {
                        "rich_text": [{"type": "text", "text": {"content": code_blocks[index]['content']}}],
                        "language": code_blocks[index]['lang'] if code_blocks[index]['lang'] in VALID_LANGUAGES else "plain text"
                    }
                })
            elif part.strip():
                children.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": part.strip()}}]}
                })
        
        return children
    pass