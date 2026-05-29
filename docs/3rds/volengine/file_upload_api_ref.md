POST https://ark.cn-beijing.volces.com/api/v3/files
本文介绍使用 Files API 上传文件请求时的输入输出参数，供您使用接口时查阅字段含义。

鉴权说明
快速入口

本接口支持 API Key /Access Key 鉴权，详见鉴权认证方式。

请求参数
跳转 响应参数
请求体

file file 必选
需要上传的文件，要求为二进制文件。具体限制请参见 Files API教程。

purpose  string 默认值：user_data 必选
文件用途。
user_data：可以灵活使用的文件，能够用于任意用途。

preprocess_configs object / null
用于设置不同文件类型的预处理规则。
属性

preprocess_configs.video.fps float / null 默认值：1
取值范围：[0.2，5]。
每秒钟从视频中抽取指定数量的图像。取值越高，对于视频中画面变化理解越精细；取值越低，对于视频中画面变化感知减弱，但是使用的token花费少，速度也更快。单视频token 用量范围在[10k, 80k]，具体参见视频理解。

preprocess_configs.video.model string
使用该文件进行推理时，要使用的视频理解模型 ID （Model ID）或 Endpoint ID。
说明
Files API 中设置的模型 ID 与推理使用的模型 ID 不强耦合，只影响上传视频文件时预处理抽帧策略。关于预处理抽帧策略，参见抽帧策略。
传入模型 ID：传入不同的模型 ID 会采用不同的抽帧策略。
传入 Endpoint ID：会按照上传时 Endpoint ID 映射的模型对应的抽帧策略进行抽帧。
不传该参数时：默认采用doubao-seed-1.8之前的模型对应的抽帧策略。
注意
doubao-seed-1.8及后续模型支持更长的视频理解能力，抽帧数已从 640 帧提升至 1280 帧。
如果要使用doubao-seed-1-8-251228进行视频理解，但通过 Files API 上传文件时未设置该模型 ID，则采用的是doubao-seed-1.8之前模型对应的抽帧策略，模型实际理解的帧数会减少。

expire_at integer 默认值：当前时刻+604800
取值范围：[当前时刻+86400, 当前时刻+2592000]，即最少保留1天，最多保留30天。
设置存储的有效期，需要传入UTC Unix时间戳（单位：秒）。
响应参数
跳转 请求参数
模型会返回对应的 file object。