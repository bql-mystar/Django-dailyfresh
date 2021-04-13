# 使用celery
from celery import Celery
from django.conf import settings
from django.core.mail import send_mail
import time
from django.template import loader

# 注意：下面注释部分在Linux系统下必须把注释给去掉，这是对django项目进行初始化，这个初始化wsgi已经帮我们进行了，但是在Linux下没有
# import django
import os
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dailyfresh.settings')
# django.setup()

# 注意：以下导入部分是导入django项目里面的内容，所以必须在django初始化之后进行导入，因此不能放在顶部，需要放在django初始化之后
from apps.goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner

# 创建一个celery对象
app = Celery('celery_tasks.tasks', broker='redis://192.168.0.12:6379/8')

# 定义任务函数
@app.task
def send_register_active_email(email, username, res):
    active_email = 'http://127.0.0.1:8000/user/active/' + res
    # 发送激活邮件    邮件链接为/user/active/user_id
    subject = '天天生鲜欢迎信息'
    html_message = "<h1>%s,欢迎成为天天生鲜注册会员</h1>请点击下面链接激活您的账户<br /><a href='%s'>%s</a>" % (username, active_email, active_email)
    from_email = settings.EMAIL_FROM
    recipient_list = [email]
    send_mail(subject, '', from_email, recipient_list, html_message=html_message)
    time.sleep(5)

@app.task
def generate_static_index_html():
        '''显示首页'''
        # 获取商品的种类信息
        types = GoodsType.objects.all()
        # 获取首页轮播商品信息
        goods_banner = IndexGoodsBanner.objects.all().order_by('index')
        # 获取首页促销活动信息
        promotion_banners = IndexPromotionBanner.objects.all().order_by('index')
        # 获取首页分类商品展示信息
        for type in types:
            # 获取type种类首页分类商品的图片展示信息
            image_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by('index')
            # 获取type种类首页分类商品的文资展示信息
            title_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by('index')
            # 动态分配type属性，分别保存首页分类商品的图片展示信息和文字展示信息
            type.image_banners = image_banners
            type.title_banners = title_banners
        # 获取用户购物车中商品数目
        cart_count = 0
        # 组织模板上下文
        context = {
            'types': types,
            'goods_banner': goods_banner,
            'promotion_banners': promotion_banners
        }
        # 加载模板文件
        temp = loader.get_template('static_index.html')
        # 模板渲染
        static_index_html = temp.render(context)
        # 生成首页对应的静态文件
        save_path = os.path.join(settings.BASE_DIR, 'static/index.html')
        with open(save_path, 'w') as f:
            f.write(static_index_html)
