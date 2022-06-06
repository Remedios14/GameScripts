#!/usr/bin/env

import cv2
import numpy as np
import sys
import win32api
import win32con
import win32gui
import win32print
import time
from PIL import ImageGrab

def intLerp(a, b, t):
    return int((1-t)*a+t*b)

def varCompare(pre, cur, l = 0):
    hist1 = cv2.calcHist([pre], [l], None, [256], [0, 256])
    hist2 = cv2.calcHist([cur], [l], None, [256], [0, 256])
    
    h1 = hist1[:, 0]
    h2 = hist2[:, 0]
    # 这里理论上不应该用前一帧该通道的均值，而用其值与黄色在该通道下的值的差值更好，但是我也就说说
    res = (h2 - h1).var() / 256
    res = res / pre[:, :, l].mean()
    return res

class FishBar():
    # TODO: 捕鱼的操作可以再优化一下；如果能检测出鱼框上下边界，考虑进碰撞的反弹，那可以试试强化学习    
    def __init__(self):
        self.cur_speed = 0.0
        self.last_top = 420
        self.vert_mid = 0
        self.inited = False
        self.mouse_down = False
    
    def update(self, brect, frect, dt):
        bar2f = brect[1] - (frect[1] + frect[3])
        fish2b = frect[1] - (brect[1] + brect[3])
        self.cur_speed = (self.last_top - brect[1]) / dt
        self.last_top = brect[1]
        if bar2f > 0:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        elif fish2b > 0:
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
        else:
            if self.cur_speed < 0 or \
                (frect[1] + frect[3] / 2) < (brect[1] + brect[3] / 2):
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
            else:
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
    def clear(self):
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
            

class FishingScript():
    def __init__(self):
        self.whandle = None
        self.left_top = (0, 0)
        self.h_width = 0
        self.h_height = 0
        self.wind_prop = 1.0
        # 识别叹号的阈值，越大越不容易误识别，可视输出调整
        self.marker_thresh = 0.3
        self.shot_t = 0.1
        # 确定人物所在位置
        self.cha_hmid = 0
        self.cha_vmid = 0
        
    # 激活窗口并放置鼠标
    def activateWnd(self, hsv):
        l, t, r, b = win32gui.GetWindowRect(hsv)
        # 若处于缩略窗口就先切换正常显示
        if r < 0:
            win32gui.ShowWindow(hsv, win32con.SW_SHOWNORMAL)
        win32gui.SetForegroundWindow(hsv)
        l, t, r, b = win32gui.GetWindowRect(hsv)
        proportion = round(win32print.GetDeviceCaps(win32gui.GetDC(0), win32con.DESKTOPHORZRES)/win32api.GetSystemMetrics(0), 2)
        
        self.setWindowProp((l, t, r, b), proportion)
        win32api.SetCursorPos((intLerp(l, r, 0.5), intLerp(t, b, 0.5)))
        win32gui.SetForegroundWindow(self.whandle)
        cv2.waitKey(1)
        
    # 截屏整个游戏窗口
    def grabFullImg(self):
        l, t, r, b = win32gui.GetWindowRect(self.whandle)
        l = int(l * self.wind_prop)
        t = int(t * self.wind_prop)
        r = int(r * self.wind_prop)
        b = int(b * self.wind_prop)
        bbox = (l, t, r, b)
        img = ImageGrab.grab(bbox)
        img_cv = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
        return img_cv
    
    # 定时甩杆
    def FisherOut(self, svtime = 1.03):
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        time.sleep(svtime) # 1.02 和 1.03 都能 max；不知道是否和钓鱼等级有关
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)

    # 赋值
    def setWindowProp(self, bbox, prop):
        self.left_top = (bbox[0], bbox[1])
        self.h_width = bbox[2] - bbox[0]
        self.h_height = bbox[3] - bbox[1]
        self.wind_prop = prop
        self.cha_hmid = self.left_top[0] + self.h_width // 2
        self.cha_vmid = self.left_top[1] + self.h_height // 2
        
    # 截屏部分窗口
    def grabRangeImg(self, bbox):
        img = ImageGrab.grab(bbox)
        img_cv = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
        return img_cv
    
    # 前期测试时截屏采样用
    def debugShot(self, bbox, shape, nums = 20):
        for i in range(nums):
            time.sleep(self.shot_t)
            img = self.grabRangeImg(bbox)
            if shape[0] != 0:
                img = cv2.resize(img, dsize = shape)
            print("image write ", i)
            cv2.imwrite("tmp/no{}.png".format(i), img)
    
    # 等待🐟上钩，即叹号出现
    def waitMarker(self):
        # TODO: 目前仅考虑人物位于屏幕中央，条件允许后续加上检测，如识别人物的轮廓转换为矩形区域来确定叹号区域
        width = self.h_width / 80
        height = self.h_height / 16
        h_mid = self.left_top[0] + self.h_width / 2
        v_mid = self.left_top[1] + self.h_height / 2
        val_list = [self.cha_hmid, self.cha_vmid - height * 2, self.cha_hmid + width, self.cha_vmid - height]
        bbox = tuple(int(x * self.wind_prop) for x in val_list)
        # self.debugShot(bbox,(60, 180))
        pre = cv2.resize(self.grabRangeImg(bbox), dsize=(60, 180))
        timer = 0.0
        while True:
            time.sleep(self.shot_t)
            timer += self.shot_t
            cur = cv2.resize(self.grabRangeImg(bbox), dsize=(60, 180))
            vared = self.imgCompare(pre, cur)
            pre = cur
            if vared:
                print("fish caught!")
                time.sleep(0.2) 
                # 捕获到感叹号有时没法正确发送左击指令，可能是 python 非严格串行的原因，多执行几次
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, int(h_mid), int(v_mid))
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0) 
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, int(h_mid), int(v_mid))
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, int(h_mid), int(v_mid))
                # win32gui.SendMessage(self.whandle, win32con.WM_LBUTTONDOWN,win32con.MK_LBUTTON,win32api.MAKELONG(8,30))
                time.sleep(0.1)
                win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
                # win32gui.SendMessage(self.whandle,win32con.WM_LBUTTONUP,win32con.MK_LBUTTON,win32api.MAKELONG(8,30))
                break
            if timer > 7.0:
                print("Wait for too long, might too large threshold")
                self.marker_thresh -= 0.05
                return False
        if timer < 0.2:
            print("Too fast, might occured misdetection")
            self.marker_thresh += 0.05
        return True
            
    # 用于判断是否出现叹号
    def imgCompare(self, pre, cur):
        jv1 = varCompare(pre, cur)
        jv2 = varCompare(pre, cur, 1)
        jv3 = varCompare(pre, cur, 2)
        print(jv1, jv2, jv3)
        blue = jv1 > self.marker_thresh
        green = jv2 > self.marker_thresh
        red = jv3 > self.marker_thresh
        if int(blue) + int(green) + int(red) > 1:
            return True
        return False
        
    # 追踪鱼条执行鼠标动作
    def traceBar(self):
        fb = FishBar()
        width = self.h_width / 8
        height = self.h_height / 20
        val_list = [self.cha_hmid - width, self.cha_vmid - 7 * height, self.cha_hmid + width, self.cha_vmid + 5*height]
        bbox = tuple(int(x * self.wind_prop) for x in val_list)
        box_w = 320
        box_h = 460
        
        round_ticker = 0 # 连续三次未捕获到符合的目标则退出该函数
        smknl = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        lgknl = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        while True:
            time.sleep(self.shot_t)
            round_ticker += 1
            if round_ticker > 3:
                break
            
            cur = cv2.resize(self.grabRangeImg(bbox),dsize=(box_w, box_h))
            b, g, r = cv2.split(cur)
            fish = cv2.subtract(cv2.subtract(b, r), cv2.subtract(b, g))
            fish = cv2.threshold(fish, 100, 255, cv2.THRESH_BINARY)[1]
            fish = cv2.morphologyEx(fish, cv2.MORPH_OPEN, smknl)
            fish = cv2.dilate(fish, lgknl)
            fcons, _ = cv2.findContours(fish, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            if len(fcons) < 1:
                print("Fish miss detected, need further check")
                continue
            frect = cv2.boundingRect(fcons[0])
            if not fb.inited:
                fb.vert_mid = frect[0] + frect[2] // 2
                fb.inited = True
            
            bina = cv2.threshold(cv2.subtract(g, r), 50, 255, cv2.THRESH_BINARY)[1]
            erd = cv2.erode(bina, smknl)
            adjed = cv2.morphologyEx(erd, cv2.MORPH_CLOSE, lgknl)
            cons, _ = cv2.findContours(adjed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            rect_list = []
            for (i, c) in enumerate(cons):
                rect = cv2.boundingRect(c)
                # 根据位置、形状筛选
                """
                if rect[2] > 32 or rect[3] > 200:
                    continue
                if (rect[0] > 80 and rect[0] < 240):
                    continue
                if rect[0] < 20 or rect[0] > 280:
                    continue
                if rect[3] < rect[2] / 2 or rect[3] < 32:
                    continue
                """
                if abs(rect[0] - fb.vert_mid) > frect[2]:
                    continue
                if len(rect_list) == 0:
                    rect_list.append(rect)
                elif rect_list[-1][3] < rect[3]:
                    rect_list.append(rect)
            if len(rect_list) < 1:
                print("Bar miss detected, need further check")
                continue
            fb.update(rect_list[-1], frect, self.shot_t * round_ticker)
            round_ticker = 0 # 顺利更新，归 0
        fb.clear()
    
    def fishComfirm(self):
        box_w = self.h_width / 10
        box_h = self.h_height / 12
        val_list = [self.cha_hmid - box_w, self.cha_vmid - 3.5 * box_h, self.cha_hmid + box_w, self.cha_vmid - box_h]
        bbox = tuple(int(x * self.wind_prop) for x in val_list)
        img = self.grabRangeImg(bbox)
        knl = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        bing = cv2.threshold(gray, 230, 255, cv2.THRESH_BINARY)[1]
        res = cv2.dilate(bing, knl)
        cons, _ = cv2.findContours(res, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if len(cons) < 1:
            return False
        rects = []
        for c in cons:
            rect = cv2.boundingRect(c)
            sur = rect[2] * rect[3]
            if len(rects) < 1:
                rects.append(rect)
            elif rects[-1][2] * rects[-1][3] < sur:
                rects.append(rect)
            continue
        if rects[-1][2] * rects[-1][3] * 2 > img.shape[0] * img.shape[1]:
            return True
        return False
            
    def loop(self):
        while True:
            print("Start one loop")
            self.FisherOut()
            time.sleep(1.5) # 完成下杆
            caught = self.waitMarker()
            if not caught:
                self.FisherOut(0.01)
                time.sleep(1.5)
                continue
            time.sleep(1.2) # 进入浮标控制
            self.traceBar()
            time.sleep(1)
            confirmed = self.fishComfirm()
            if confirmed:
                self.FisherOut(0.01)
            time.sleep(1)
            print("Finish one loop")

    def work(self):
        hsv = win32gui.FindWindow("SDL_app", "Stardew Valley")
        if hsv == 0:
            win32api.MessageBeep()
            ret = win32api.MessageBox(0, "未找到运行中的窗口，请打开游戏再运行此脚本", "注意")
            if ret == 1:
                sys.exit(0)
        self.whandle = hsv
        self.activateWnd(hsv)
        # TODO: 可以加上按键终止、启动循环
        self.loop()
    
def main():
    fs = FishingScript()
    print("Object created")
    fs.work()
    
def other():
    imglist = []
    for j in range(20):
        imglist.append(cv2.imread("tmp/no{}.png".format(j)))
    

if __name__ == "__main__":
    main()