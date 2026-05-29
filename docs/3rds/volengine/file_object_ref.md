上传文件或检索文件后，模型会返回一个 file 对象。本文为您介绍 file 对象包含的详细参数。

object string
固定为file。

id string
文件的唯一标识符。

purpose string
文件用途。

bytes integer
文件大小，以bytes为单位。仅文件处理状态为active时返回。

created_at integer
本次请求上传文件时的Unix时间戳(秒)。

expire_at integer
文件过期时间的Unix时间戳（秒）。

mime_type string
文件的MIME类型，如application/pdf。仅文件处理状态为active时返回。

status string
文件处理状态。
processing：文件正在预处理，无法使用。
active：文件已处理完成，可以使用。
failed：文件上传失败，错误详情查看error字段。

error object / null
文件上传失败时返回的错误对象，即status取值为failed时才会返回该字段。
code：错误码。
message：错误描述信息。

preprocess_configs object / null
用于设置不同文件类型的预处理规则。
属性
preprocess_configs.video.fps float / null
每秒钟从视频中抽取指定数量的图像。取值越高，对于视频中画面变化理解越精细；取值越低，对于视频中画面变化感知减弱，但是使用的token花费少，速度也更快。

preprocess_configs.video.model string
使用该文件进行推理时，要使用的视频理解模型 ID （Model ID）或 Endpoint ID。
