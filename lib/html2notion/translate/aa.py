import hashlib
import requests
import time
import pymysql
import json
from typing import Optional
from urllib.parse import urlparse, parse_qs, urlencode
res = {}


def generate_signed_url(url, app_secret):
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)

    # 删除 sign 参数（如果存在）
    if "sign" in query_params:
        del query_params["sign"]

    # 对参数名进行升序排序并拼接
    sorted_params = sorted(query_params.items(), key=lambda x: x[0])
    concatenated_params = "".join(f"{k}{v[0]}" for k, v in sorted_params)

    # print(concatenated_params)
    # 将 APPSECRET 添加到字符串首部
    string_to_hash = app_secret + concatenated_params

    # 使用 MD5（32位）摘要算法，并将结果全部转为大写
    md5_hash = hashlib.md5(string_to_hash.encode()).hexdigest().upper()

    # 将 sign 参数添加到原始参数中并生成最终 URL
    query_params["sign"] = [md5_hash]
    final_query_string = urlencode(query_params, doseq=True)
    signed_url = parsed_url._replace(query=final_query_string).geturl()

    return signed_url


def get_book_list(app_key: str, app_secret: str, book_type: Optional[int] = None,
                  page_index: Optional[int] = None) -> dict:
    base_url = "https://openapi.yuewen.com/cprealtime/v1/book/getbooklist"
    
    timestamp = int(time.time() * 1000)  # 获取当前时间戳（毫秒）
    # 构建请求参数
    params = {
        "appkey": app_key,
        "timestamp": timestamp,
    }

    if book_type is not None:
        params["type"] = book_type

    if page_index is not None:
        params["pageIndex"] = page_index

    # 生成签名后的完整 URL
    url_with_query = base_url + "?" + urlencode(params)
    signed_url = generate_signed_url(url_with_query, app_secret)

    # print(signed_url)
    # 发送请求并解析响应
    response = requests.get(signed_url)
    response_data = response.json()

    return response_data

def get_book_ids_by_cbids(cbids: list, batch_size: int = 100) -> list:
    # 连接到 MySQL 数据库
    connection = pymysql.connect(
        host="9.142.184.5",
        user="gyaccounts",
        password="gy@2018yw",
        database="wereadstoresvr"
    )
    cursor = connection.cursor()

    book_ids = []

    # 分批查询
    for i in range(0, len(cbids), batch_size):
        batch_cbids = cbids[i:i + batch_size]
        cbids_str = ','.join(str(cbid) for cbid in batch_cbids)
        query = f"select bid from `book_cbids` where `cbid` IN ({cbids_str});"

        # 执行查询
        cursor.execute(query)

        # 获取查询结果
        book_ids.extend([row[0] for row in cursor.fetchall()])

    # 关闭连接
    cursor.close()
    connection.close()

    return book_ids

def HTTPPost(url, data={}, header={}, files={}, params={}):
    try:
        r = requests.post(url, timeout=5, data=data, headers=header, files=files, params=params)

    except requests.ConnectionError as e:
        return ""
    except requests.exceptions.Timeout as e:
        return ""
    except requests.exceptions.TooManyRedirects as e:
        return ""
    except requests.exceptions.RequestException as e:
        return ""

    if r.status_code == 200:
        return r.text
    elif r.status_code == 499:
        return r.text
    else:
        return ""

def DoSetStrkv(strkey: str, value: str):
    url = "http://wr.qq.com:8080/strkvoper"
    timestamp = round(time.time())
    salt = "B0hsWpOXaMThWGG4"
    cmd = "set"
    oroginal = str(timestamp) + salt + cmd + strkey
    md5 = hashlib.md5()
    md5.update(oroginal.encode('utf-8'))
    signature = md5.hexdigest()

    payload = json.dumps(
    {
        "cmd": cmd,
        "key": strkey,
        "timestamp": timestamp,
        "signature": signature,
        "seq": timestamp,
        "value": value
    }
    )
    header = {'Content-Type': 'application/json'}

    response = HTTPPost(url, data=payload, header=header)
    if not response:
        res["error"] = "更新存储失败"

    rsp = json.loads(response)
    if "succ" not in rsp or rsp["succ"] != 1:
        res["error"] = "更新存储失败"
        res["msg"] = response
    return
    

def check_update(book_ids: list, strkv_key: str):
    # http://wr.qq.com:8080/strkvoper?key=custom/encodebooks
    data_url = 'http://wr.qq.com:8080/strkvoper?key=' + strkv_key
    response = requests.get(data_url)
    old_data = response.json().get('value', {})
    old_bids = old_data.get("bookids", []) if old_data else []
    need_update = False
    if len(book_ids) != len(old_data):
        need_update = True
    else:
        for bookid in book_ids:
            if bookid not in old_data:
                need_update = True
                break
    if not need_update:
        return False

    # 更新 strkv
    new_data = {"bookids": book_ids, "updatetime": int(time.time())}
    DoSetStrkv(strkv_key, json.dumps(new_data))
    return True


def main():
    # 示例用法
    app_key = "f31f53580000023"
    app_secret = "a19685111e1348ba22c74ae24bf8ca0a"

    # 0: 反盗版内容水印书单
    # 1：单书门槛书单
    book_type = 0
    page_index = 0
    result = get_book_list(app_key, app_secret, book_type, page_index)

    if result.get('code', -1) != 0:
        res["err"] = '从阅文拿花生计划列表失败'
        print(json.dumps(res))
        sys.exit(-1)

    total = result['data']['total']
    cbids = result['data']['cbids']
    res['total'] = total
    book_ids = get_book_ids_by_cbids(cbids)
    if len(book_ids) != total:
        res["err"] = '花生计划书籍转换结果不一致'
        res["book_ids"] = book_ids
        res["cbids"] = cbids
        print(json.dumps(res))
        sys.exit(-1)

    is_update = check_update(book_ids, "custom/encodebooks_prepare")
    res["is_update"] = is_update

    # 
    page_index = 0
    book_type = 1
    result = get_book_list(app_key, app_secret, book_type, page_index)
    if result.get('code', -1) != 0:
        res["err"] = '从阅文拿重点书列表失败'
        print(json.dumps(res))
        sys.exit(-1)

    total_block = result['data']['total']
    res['total_block'] = total_block
    block_cbids = result['data']['cbids']
    block_book_ids = get_book_ids_by_cbids(block_cbids)
    if len(block_book_ids) != total_block:
        res["err"] = '重点书转换结果不一致'
        res["block_cbids"] = block_cbids
        res["block_book_ids"] = block_book_ids
        print(json.dumps(res))
        sys.exit(-1)

    is_update_block = check_update(block_book_ids, "custom/ywblock_prepare")
    res["is_update_block"] = is_update_block
    # print(book_ids)

if __name__ == '__main__':
    main()
