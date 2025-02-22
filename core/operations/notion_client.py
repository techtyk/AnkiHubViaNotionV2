# 封装 Notion API 的操作，处理与外部系统的交互

from notion_client import Client
import traceback


class NotionClient:
    def __init__(self, token):
        """
        初始化 NotionClient 实例，接收 token 并创建 Notion SDK 的 Client 实例
        """
        self.token = token
        self.client = Client(auth=token)

    def batch_update_database(self, database_id, notes_data,config):
        """
        批量更新 Notion 数据库：
          - copy 模式直接创建新页面，不检查重复
          - 对于其它模式：如果存在重复页面，则根据模式进行覆盖或跳过；如果无重复，则创建新页面
        返回一个字典：{'success': [...], 'failed': [...]}
        """
        success = []
        failed = []

        for note_data in notes_data:
            try:
                # 每次循环时从最新的配置中读取处理模式
                mode = config.get("duplicate_handling_way", "keep").lower()

                # copy 模式：直接创建新页面
                if mode == "copy":
                    create_response = self.client.pages.create(
                        parent={'database_id': database_id},
                        properties=note_data['properties'],
                        children=note_data.get('children', [])
                    )
                    success.append({
                        'operation': note_data,
                        'action': 'create',
                        'page_id': create_response['id'],
                        'response': create_response,
                    })
                    continue

                # 其它模式：先进行重复检查
                dup_filter = note_data['duplicate_check']['filter']
                query = self.client.databases.query(database_id=database_id, filter=dup_filter)
                # 如果存在重复页面
                if query.get('results'):
                    if mode == "overwrite":
                        # 覆盖：更新已存在页面
                        page_id = query['results'][0]['id']
                        update_response = self.client.pages.update(
                            page_id=page_id,
                            properties=note_data['properties'],
                            children=note_data.get('children', [])
                        )
                        success.append({
                            'operation': note_data,
                            'action': 'update',
                            'page_id': page_id,
                            'response': update_response,
                        })
                    elif mode == "keep":
                        # 保留：跳过更新，保持现有页面
                        success.append({
                            'operation': note_data,
                            'action': 'skip',
                            'page_id': query['results'][0]['id'],
                            'response': None,
                        })
                    else:
                        # 默认情况，同 keep
                        success.append({
                            'operation': note_data,
                            'action': 'skip',
                            'page_id': query['results'][0]['id'],
                            'response': None,
                        })
                else:
                    # 若不存在重复，则创建新的 Notion 页面
                    create_response = self.client.pages.create(
                        parent={'database_id': database_id},
                        properties=note_data['properties'],
                        children=note_data.get('children', [])
                    )
                    success.append({
                        'operation': note_data,
                        'action': 'create',
                        'page_id': create_response['id'],
                        'response': create_response,
                    })
            except Exception as e:
                traceback.print_exc()
                failed.append({
                    'operation': note_data,
                    'error': str(e),
                    'trace': traceback.format_exc()
                })

        return {
            'success': success,
            'failed': failed
        }