


class Note:
    # Note类负责提取和写入anki数据

    

    @staticmethod
    def get_meta_fields_from_anki(note):
        """从anki数据库中提取元数据字段（参考 anki2notion.py 207-261 行）"""
        card = note.cards()[0] if note.cards() else None
        meta_fields_from_anki={
            "Anki ID": str(note.id),
            "Deck": mw.col.decks.get(card.did)["name"] if card else "",
            "Tags": ", ".join(note.tags),
            "Note Type": note.note_type()["name"] if note.note_type() else "",
            "Card Type": card.type,
            "First Field": list(note.keys())[0] if note.keys() else "",
            "Creation Time": datetime.fromtimestamp(note.id / 1000 ,tz=datetime.now().astimezone().tzinfo).isoformat(),
            "Modification Time": datetime.fromtimestamp(note.mod,tz=datetime.now().astimezone().tzinfo).isoformat(),
            "Due Date": Note.get_card_due_date(card).isoformat() if Note.get_card_due_date(card) else None,  # 空值设为None避免发送空字符串
            "Review Count": card.reps if card else 0,
            "Ease Factor": card.factor / 1000 if card else 0,
            "Interval": card.ivl if card else 0,
            "Lapses": card.lapses if card else 0,
            "Suspended":card.queue == -1,
        }
        meta_fields_from_anki = Note.write_fsrs_data(note, meta_fields_from_anki)
        return meta_fields_from_anki
    @staticmethod
    def get_card_due_date(card):
        """根据卡片信息获取到期日期"""
        import time

        col = mw.col
        if card.queue < 0:
            # 卡片被挂起或已删除
            return None
        elif card.type == 0:
            # 新卡片，due 表示新卡位置，无法确定具体日期
            return None
        elif card.type == 1:
            # 学习中卡片，due 是相对时间，单位为秒
            due = time.time() + (card.due * 60)
            return datetime.fromtimestamp(due)
        elif card.type == 2:
            # 复习卡片，due 是天数
            due = (card.due - col.sched.today) * 86400 + time.time()
            return datetime.fromtimestamp(due)
        else:
            return None
    @staticmethod
    def write_fsrs_data(note, properties):
        # 从数据库直接获取卡片数据（兼容 Anki 24.11+）
        card = note.cards()[0]
        try:
            # 使用 Anki 数据库查询获取原始数据
            card_data = mw.col.db.scalar(
                "SELECT data FROM cards WHERE id = ?", card.id
            )
            
            if card_data:
                # 使用 FSRS Helper 的解析方式
                card_data_json = json.loads(card_data)
                # 提取 FSRS 参数（使用 FSRS Helper 的字段名）
                if 'd' in card_data_json:  # 难度
                    properties['Difficulty'] = {'number': card_data_json['d']}
                if 's' in card_data_json:  # 稳定性
                    properties['Stability'] = {'number': card_data_json['s']}
                if 'dr' in card_data_json:  # 可提取性
                    properties['Retrievability'] = {'number': card_data_json['dr']}
                    
        except Exception as e:
            print(e)
        return properties