# Fedex Tracking Bot

[English](./README.md) | 中文

## 概述

该项目旨在通过Excel文件中的追踪号码自动化追踪货运状态。通过使用网络抓取技术，程序从FedEx网站获取实时追踪信息，并将结果存储在一个新的Excel文件中。

## 功能

- **自动追踪**：自动获取一系列货运号码的追踪状态。
- **并发处理**：利用多线程同时处理多个追踪号码，提高效率。
- **代理支持**：支持代理设置，以确保匿名性并绕过区域限制。
- **错误处理**：包含重试机制以处理临时网络问题或网站不可用的情况。

## 要求

- Python 3.x
- Selenium
- BeautifulSoup
- pandas
- openpyxl
- 项目目录中有效的ChromeDriver可执行文件

## 设置

1. 安装所需的Python包：

2. 下载并将ChromeDriver可执行文件放入项目目录。

3. 编辑项目目录中的`.env`文件
   ```plaintext
   # 包含追踪号码的输入Excel文件名
   INPUT_FILE=input_example.xlsx

   # 用于网络请求的代理地址。如果不需要代理，请将此参数留空。
   PROXY_ADDRESS=socks5://127.0.0.1:8443

   # 最大并发工作者数量
   MAX_WORKERS=10
   
   # chromedriver.exe路径
   CHROME_DRIVER_PATH=./chromedriver.exe
   ```

4. 运行脚本：
   ```bash
   python main.py
   ```

## 使用

- 确保`.env`文件中指定的输入Excel文件存在于项目目录中。
- 脚本将生成一个包含追踪结果的输出Excel文件，命名为`tracking_resultsN.xlsx`。

## 注意事项

- 确保ChromeDriver版本与已安装的Chrome浏览器版本匹配。
- 根据系统能力调整`.env`文件中的`MAX_WORKERS`设置以获得最佳性能。
- 请求过多（通常100次查询左右）会被禁止访问一段时间，推荐使用[glider项目](https://github.com/nadoo/glider)，可以将多个代理节点批量转换为代理池。
- 如果不需要设置代理，置空env中`PROXY_ADDRESS`参数即可，但是查询次数会受到限制。

## 运行结果
![Result](./img.png)