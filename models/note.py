# 封装笔记数据模型

# 数据模型（根据需求文档3.5）
class Note:
    def __init__(self, anki_note):
        self.fields = self._extract_fields(anki_note)
        self.metadata = self._extract_metadata(anki_note)
    
    def _extract_fields(self, anki_note):
        """提取模板字段（根据需求文档3.5）"""
        return {f: anki_note[f] for f in anki_note.keys()}
    
    def _extract_metadata(self, anki_note):
        """提取元数据（根据需求文档4.2.1）"""
        card = anki_note.cards()[0]
        return {
            'card_id': anki_note.id,
            'deck': anki_note.deck,
            'tags': anki_note.tags,
            'due_date': card.due,
            'interval': card.ivl,
            'ease_factor': card.factor
        }