#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os
import datetime
import requests
import time
import threading
import logging
from PIL import Image, ImageDraw, ImageFont
import traceback

picdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'pic')
libdir = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), 'lib')
if os.path.exists(libdir):
    sys.path.append(libdir)

logging.basicConfig(level=logging.DEBUG)

# 全局变量，用于控制显示位置的交替和IP更新
position_swap = False
running = True
public_ip = "获取中..."  # 初始IP显示
last_ip_update = 0  # 上次更新IP的时间戳

# 自定义Mock类，用于在没有硬件时进行测试
class MockEPD:
    def __init__(self):
        self.width = 122
        self.height = 250
        logging.info("已初始化MockEPD")
    
    def init(self):
        logging.info("模拟初始化")
        
    def Clear(self):
        logging.info("模拟清屏")
    
    def getbuffer(self, image):
        logging.info("模拟获取缓冲区")
        return "buffer"
    
    def display(self, black_buffer, red_buffer):
        logging.info("模拟显示 - 在真实硬件上会显示")
        # 显示关于将要显示内容的调试信息
        logging.info(f"位置互换: {position_swap}")
    
    def sleep(self):
        logging.info("模拟休眠")

def get_ip_address():
    """获取公网IP地址，带有后备选项"""
    try:
        # 尝试多个IP API，以防某个失败
        apis = [
            "http://ip.3322.net",
            "https://api.ipify.org",
            "https://ifconfig.me/ip"
        ]
        
        for api in apis:
            try:
                response = requests.get(api, timeout=5)
                if response.status_code == 200:
                    ip = response.text.strip()
                    if ip and len(ip) < 30:  # 基本验证
                        return ip
            except:
                continue
                
        # 如果所有外部API都失败，尝试获取本地IP
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return f"本地: {local_ip}"
    except Exception as e:
        logging.error(f"所有IP获取方法都失败了: {e}")
        return "IP获取失败"

def update_ip_if_needed():
    """每24小时更新一次IP地址"""
    global public_ip, last_ip_update
    current_time = time.time()
    
    # 检查是否需要更新IP（24小时 = 86400秒）
    if current_time - last_ip_update >= 86400 or last_ip_update == 0:
        logging.info("开始获取公网IP地址（24小时更新）")
        public_ip = get_ip_address()
        last_ip_update = current_time
        logging.info(f"更新IP: {public_ip}")
    else:
        hours_left = 24 - (current_time - last_ip_update) / 3600
        logging.info(f"使用缓存IP: {public_ip}，距离下次更新还有约{hours_left:.1f}小时")

def display_info():
    global position_swap
    
    try:
        logging.info("开始电子墨水屏显示")
        
        # 尝试导入真实模块，如果失败则回退到模拟模式
        try:
            from waveshare_epd import epd2in13b_V4
            epd = epd2in13b_V4.EPD()
            logging.info("使用真实电子墨水屏")
        except Exception as e:
            logging.warning(f"初始化真实显示失败: {e}")
            logging.info("改为使用模拟显示")
            epd = MockEPD()
        
        logging.info("初始化并清屏")
        epd.init()
        epd.Clear()
        
        # 加载字体
        logging.info("加载字体")
        # 尝试加载字体，带有后备选项
        try:
            font28 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 28)
            font20 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 20)
            font16 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 16)
            font14 = ImageFont.truetype(os.path.join(picdir, 'Font.ttc'), 14)
        except:
            # 回退到默认字体
            font28 = ImageFont.load_default()
            font20 = ImageFont.load_default()
            font16 = ImageFont.load_default()
            font14 = ImageFont.load_default()
            logging.warning("使用默认字体")
            
        # 首次获取IP
        update_ip_if_needed()
        
        while running:
            # 更新IP（如果需要）
            update_ip_if_needed()
            
            # 创建水平显示图像
            logging.info("创建日期和IP显示图像") 
            HBlackimage = Image.new('1', (epd.height, epd.width), 255)  # 250*122
            HRYimage = Image.new('1', (epd.height, epd.width), 255)  # 250*122
            drawblack = ImageDraw.Draw(HBlackimage)
            drawry = ImageDraw.Draw(HRYimage)
            
            # 获取当前日期
            now = datetime.datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            
            # 直接转换为中文星期
            weekday_dict = {
                0: "星期一",
                1: "星期二",
                2: "星期三",
                3: "星期四",
                4: "星期五",
                5: "星期六",
                6: "星期日"
            }
            weekday_cn = weekday_dict[now.weekday()]
            
            # 添加鼓励语
            motto = "深呼吸、放轻松、没什么大不了的"
            
            # 根据position_swap的值决定日期和IP的显示位置
            if position_swap:
                # 在顶部显示IP地址
                drawry.text((10, 5), f"IP: {public_ip}", font=font20, fill=0)
                # 在底部显示日期和星期
                drawblack.text((10, 40), date_str, font=font28, fill=0)
                drawblack.text((10, 70), weekday_cn, font=font20, fill=0)
                # 添加鼓励语
                drawblack.text((10, 100), motto, font=font14, fill=0)
            else:
                # 在顶部显示日期和星期
                drawblack.text((10, 5), date_str, font=font28, fill=0)
                drawblack.text((10, 35), weekday_cn, font=font20, fill=0)
                # 在中间显示鼓励语
                drawblack.text((10, 60), motto, font=font14, fill=0)
                # 在底部显示IP地址
                drawry.text((10, 85), f"IP: {public_ip}", font=font20, fill=0)
            
            # 添加边框
            drawblack.rectangle((5, 5, 245, 117), outline=0)
            
            try:
                # 显示图像
                epd.display(epd.getbuffer(HBlackimage), epd.getbuffer(HRYimage))
                logging.info(f"显示完成。位置互换: {position_swap}")
            except Exception as e:
                logging.error(f"显示失败: {e}")
                # 如果显示失败，记录本应显示的内容
                logging.info(f"本应显示日期: {date_str}, 星期: {weekday_cn}, IP: {public_ip}")
                logging.info(f"鼓励语: {motto}")
                logging.info(f"位置互换: {position_swap}")
            
            # 切换position_swap的值
            position_swap = not position_swap
            
            # 等待2小时，每秒检查一次是否需要退出
            for _ in range(7200):  # 2小时 = 7200秒
                if not running:
                    break
                time.sleep(1)
                
    except Exception as e:
        logging.error(f"display_info中的错误: {e}")
        traceback.print_exc()
        
    finally:
        cleanup()

def cleanup():
    global running
    running = False
    logging.info("正在清理...")
    try:
        # 尝试导入并使用真实模块
        try:
            from waveshare_epd import epd2in13b_V4
            epd = epd2in13b_V4.EPD()
            logging.info("使真实显示进入休眠状态...")
            epd.sleep()
        except:
            logging.info("使用模拟清理")
            MockEPD().sleep()
    except:
        pass

if __name__ == "__main__":
    try:
        # 启动主线程显示信息
        display_thread = threading.Thread(target=display_info)
        display_thread.daemon = True  # 设置为后台线程，主线程结束时自动终止
        display_thread.start()
        
        # 主线程等待键盘中断
        while running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logging.info("检测到键盘中断")
        cleanup()
        sys.exit(0)

