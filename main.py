"""
雷霆战机 - Kivy移动端版本
使用Kivy框架实现，支持Android和iOS
"""
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.clock import Clock
from kivy.graphics import Rectangle, Color, Ellipse
from kivy.core.camera import Camera
from kivy.core.image import Image as CoreImage
from kivy.properties import NumericProperty, ReferenceListProperty, ObjectProperty
from kivy.vector import Vector
from kivy.config import Config
from kivy.utils import platform
from kivy.core.window import Window
import random
from functools import partial

# 仅桌面调试时固定窗口大小；Android 上必须用全屏，
# 否则硬编码 480x600 会让 SDL 窗口开成小黑面导致启动黑屏。
if platform == 'win':
    Config.set('graphics', 'width', '480')
    Config.set('graphics', 'height', '600')
    Config.set('graphics', 'resizable', 'False')
else:
    Config.set('graphics', 'resizable', 'True')

WIDTH = 480
HEIGHT = 600
FPS = 60

def _sync_size(*args):
    """让逻辑画布跟随实际窗口尺寸。

    安卓是全屏窗口（如 1080x2400），若继续用硬编码 480x600，
    根布局只占窗口一角、其余为黑色背景，导致启动黑屏。
    这里把 WIDTH/HEIGHT 同步成当前窗口尺寸，使所有游戏坐标自动适配全屏。
    """
    global WIDTH, HEIGHT
    w, h = Window.size
    if w and h:  # 忽略尚未初始化时的 (0, 0)
        WIDTH, HEIGHT = w, h

Window.bind(size=_sync_size)
_sync_size()


class Player(Widget):
    """玩家飞机类"""
    velocity_x = NumericProperty(0)
    velocity_y = NumericProperty(0)
    velocity = ReferenceListProperty(velocity_x, velocity_y)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size = (50, 38)
        self.pos = (WIDTH/2 - 25, HEIGHT - 48)
        self.shield = 100
        self.power = 1
        self.shoot_delay = 0.25
        self.last_shot = 0
        
        # 绘制玩家飞机（绿色矩形）
        with self.canvas:
            Color(0, 1, 0, 1)
            self.rect = Rectangle(pos=self.pos, size=self.size)
    
    def update(self, dt):
        """更新玩家位置"""
        self.pos = Vector(*self.velocity) * dt + self.pos
        
        # 边界限制
        if self.x < 0:
            self.x = 0
        if self.right > WIDTH:
            self.right = WIDTH
        if self.y < 0:
            self.y = 0
        if self.top > HEIGHT:
            self.top = HEIGHT
        
        # 更新图形位置
        self.rect.pos = self.pos
    
    def shoot(self, game):
        """发射子弹"""
        import time
        current_time = time.time()
        if current_time - self.last_shot > self.shoot_delay:
            self.last_shot = current_time
            if self.power == 1:
                bullet = Bullet(pos=(self.center_x - 5, self.top))
                game.add_widget(bullet)
                game.bullets.append(bullet)
            elif self.power >= 2:
                bullet1 = Bullet(pos=(self.x, self.center_y))
                bullet2 = Bullet(pos=(self.right - 10, self.center_y))
                game.add_widget(bullet1)
                game.add_widget(bullet2)
                game.bullets.append(bullet1)
                game.bullets.append(bullet2)


class Bullet(Widget):
    """子弹类"""
    velocity_y = NumericProperty(-10)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size = (10, 20)
        
        # 绘制子弹（黄色矩形）
        with self.canvas:
            Color(1, 1, 0, 1)
            self.rect = Rectangle(pos=self.pos, size=self.size)
    
    def update(self, dt):
        """更新子弹位置"""
        self.y += self.velocity_y
        self.rect.pos = self.pos
        
        # 飞出屏幕则销毁
        if self.top < 0:
            return False
        return True


class Mob(Widget):
    """敌人类"""
    velocity_x = NumericProperty(0)
    velocity_y = NumericProperty(0)
    velocity = ReferenceListProperty(velocity_x, velocity_y)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size = (50, 38)
        self.x = random.randrange(WIDTH - 50)
        self.y = random.randrange(-100, -40)
        self.velocity_y = random.randrange(1, 8)
        self.velocity_x = random.randrange(-3, 3)
        
        # 绘制敌机（红色矩形）
        with self.canvas:
            Color(1, 0, 0, 1)
            self.rect = Rectangle(pos=self.pos, size=self.size)
    
    def update(self, dt):
        """更新敌机位置"""
        self.pos = Vector(*self.velocity) * dt + self.pos
        self.rect.pos = self.pos
        
        # 超出屏幕则重置
        if self.top > HEIGHT + 10 or self.x < -25 or self.right > WIDTH + 20:
            self.x = random.randrange(WIDTH - 50)
            self.y = random.randrange(-100, -40)
            self.velocity_y = random.randrange(1, 8)
            self.velocity_x = random.randrange(-3, 3)


class GameWidget(FloatLayout):
    """游戏主界面"""
    player = ObjectProperty(None)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 让逻辑画布跟随当前窗口尺寸，根布局填满整个窗口（安卓全屏不再黑屏）
        _sync_size()
        
        # 创建玩家
        self.player = Player()
        self.add_widget(self.player)
        
        # 游戏对象列表
        self.mobs = []
        self.bullets = []
        
        # 创建初始敌机
        for i in range(8):
            mob = Mob()
            self.add_widget(mob)
            self.mobs.append(mob)
        
        # 摄像头控制
        self.camera = None
        self.camera_active = False
        self.motion_center_x = None
        self.background_frame = None
        self.threshold = 30
        
        # 启动游戏循环
        Clock.schedule_interval(self.update, 1.0/FPS)
        
        # 延迟启动摄像头
        Clock.schedule_once(self.init_camera, 3)
    
    def init_camera(self, dt):
        """初始化摄像头（仅在有可用 provider 时启动，失败不影响游戏）"""
        try:
            from kivy.core.camera import Camera
            # 检测是否有可用的摄像头 provider，Android 上默认没打包摄像头模块时跳过
            provider = Camera.providers
            if not provider:
                print("无可用摄像头 provider，跳过摄像头控制")
                return
            self.camera = Camera(index=0, resolution=(480, 600), play=False)
            if self.camera:
                self.camera.play = True
                self.camera_active = True
                Clock.schedule_once(self.capture_background, 1)
                print("摄像头已启动")
        except Exception as e:
            print(f"摄像头初始化失败（不影响游戏）: {e}")
    
    def capture_background(self, dt):
        """捕获背景帧"""
        if self.camera and self.camera_active:
            # 获取背景帧（简化处理）
            self.background_captured = True
            print("背景已捕获")
    
    def process_camera(self):
        """处理摄像头画面，检测运动"""
        if not self.camera or not self.camera_active:
            return None
        
        # 简化版：使用摄像头中心位置
        # 实际应该使用OpenCV进行运动检测
        # 这里简化为随机移动用于演示
        return random.randint(0, WIDTH)
    
    def update(self, dt):
        """游戏主循环"""
        # 更新玩家
        self.player.update(dt)
        
        # 自动射击
        self.player.shoot(self)
        
        # 摄像头控制
        motion_x = self.process_camera()
        if motion_x is not None:
            # 镜像反转
            target_x = WIDTH - motion_x
            self.player.x = target_x - 25
        
        # 更新敌机
        for mob in self.mobs[:]:
            mob.update(dt)
        
        # 更新子弹
        for bullet in self.bullets[:]:
            if not bullet.update(dt):
                self.remove_widget(bullet)
                self.bullets.remove(bullet)
        
        # 碰撞检测（简化版）
        self.check_collisions()
    
    def check_collisions(self):
        """碰撞检测"""
        # 子弹击中敌机
        for bullet in self.bullets[:]:
            for mob in self.mobs[:]:
                if self.collide_widget(bullet, mob):
                    self.remove_widget(bullet)
                    self.bullets.remove(bullet)
                    self.remove_widget(mob)
                    self.mobs.remove(mob)
                    # 生成新敌机
                    new_mob = Mob()
                    self.add_widget(new_mob)
                    self.mobs.append(new_mob)
                    break
        
        # 敌机撞击玩家
        for mob in self.mobs[:]:
            if self.collide_widget(mob, self.player):
                self.player.shield -= 20
                self.remove_widget(mob)
                self.mobs.remove(mob)
                # 生成新敌机
                new_mob = Mob()
                self.add_widget(new_mob)
                self.mobs.append(new_mob)
                
                if self.player.shield <= 0:
                    # 游戏结束逻辑
                    pass
    
    def collide_widget(self, widget1, widget2):
        """简单的矩形碰撞检测"""
        return (widget1.x < widget2.right and
                widget1.right > widget2.x and
                widget1.y < widget2.top and
                widget1.top > widget2.y)


class ThunderFighterApp(App):
    """应用主类"""
    def build(self):
        return GameWidget()
    
    def on_stop(self):
        """应用退出时清理资源"""
        pass


if __name__ == '__main__':
    ThunderFighterApp().run()
