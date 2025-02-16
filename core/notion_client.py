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

    def batch_update_database(self, database_id, operations, retain_source):
        """
        批量更新 Notion 数据库：
          - 对于每一条操作，根据 duplicate_check 判断是否已有重复页面
          - 如果已有重复页面且配置为 'overwrite'，则更新该页面
          - 如果无重复，则创建新页面

        返回一个字典：{'success': [...], 'failed': [...]}
        """
        success = []
        failed = []
        for op in operations:
            try:
                # duplicate_check 中包含 Notion API 可用的过滤器格式
                dup_filter = op['duplicate_check']['filter']
                query = self.client.databases.query(database_id=database_id, filter=dup_filter)
                # 如果存在重复页面
                if query.get('results'):
                    if op.get('handling') == 'overwrite':
                        # 获取第一个匹配页面ID，并进行更新
                        page_id = query['results'][0]['id']
                        # 先删除旧页面再创建新页面（模仿V1版本345-382行）
                        self.client.blocks.delete(block_id=page_id)
                        # 创建新页面（携带children参数）
                        create_response = self.client.pages.create(
                            parent={'database_id': database_id},
                            properties=op['data'],
                            children=op.get('children', [])
                        )
                        success.append({
                            'operation': op,
                            'action': 'overwrite',
                            'old_page_id': page_id,
                            'new_page_id': create_response['id'],
                            'response': create_response,
                        })
                    else:
                        # 配置不是 overwrite 的情况下，跳过更新
                        success.append({
                            'operation': op,
                            'action': 'skip',
                            'page_id': query['results'][0]['id'],
                            'response': None,
                        })
                else:
                    # 无重复，则创建新的 Notion 页面，parent 参数为数据库 ID
                    create_response = self.client.pages.create(
                        parent={'database_id': database_id},
                        properties=op['data'],
                        children=op.get('children', [])
                    )
                    success.append({
                        'operation': op,
                        'action': 'create',
                        'page_id': create_response['id'],
                        'response': create_response,
                    })
            except Exception as e:
                traceback.print_exc()
                failed.append({
                    'operation': op,
                    'error': str(e)
                })
        return {'success': success, 'failed': failed}