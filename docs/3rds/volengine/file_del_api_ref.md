DELETE https://ark.cn-beijing.volces.com/api/v3/files/{file_id}
根据文件ID删除文件，并将文件从存储空间中移除。

快速入口
鉴权说明

模型列表
模型计费
模型调用教程
API Key

请求参数
路径参数

id string 必选
待删除的文件id。
响应参数

id string
被删除的文件id。

object string
固定为 file。

deleted boolean
文件被删除，取值true表明删除成功。