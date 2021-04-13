from django.shortcuts import render, redirect
from django.views.generic import View
from django.core.mail import send_mail
from celery_tasks import tasks
from django.conf import settings
from apps.user.models import User, Address
from django.urls import reverse
from itsdangerous import TimedJSONWebSignatureSerializer
from django_redis import get_redis_connection
from apps.goods.models import GoodsSKU
from itsdangerous import SignatureExpired
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from utils.mixin import LoginRequiredMixin
import re
from apps.order.models import OrderInfo, OrderGoods
from django.core.paginator import Paginator


# Create your views here.
# def register(request):
#     if request.method == 'GET':
#         '''显示注册页面'''
#         return render(request, 'register.html')
#     else:
#         '''进行注册处理'''
#         # 接收数据
#         username = request.POST.get('user_name')
#         password = request.POST.get('pwd')
#         email = request.POST.get('email')
#         allow = request.POST.get('allow')
#         # 进行数据校验
#         if not all([username, password, email]):
#             # 数据不完整
#             return render(request, 'register.html', {'errormsg': '数据不完整'})
#         # 校验邮箱
#         if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
#             return render(request, 'register.html', {'errormsg': '邮箱格式不正确'})
#         if allow != 'on':
#             return render(request, 'register.html', {'errormsg': '请同意协议'})
#         try:
#             # 判断数据库中是否有这个用户
#             user = User.objects.get(username=username)
#         except User.DoesNotExist:
#             # 如果抛出异常，说明用户不存在，也就是该用户是可用的
#             user = None
#         # 进行业务处理：进行用户注册
#         # 可以使用django自带的认证系统
#         # user = User()
#         # user.username = username
#         # user.password = password
#         # user.email = email
#         # user.save()
#         if user:
#             return render(request, 'register.html', {'errormsg': '用户名已存在'})
#         user = User.objects.create_user(username, email, password)
#         user.is_active = 0
#         user.save()
#         # 返回应答,跳转到首页
#         return redirect(reverse('goods:index'))

# 使用类视图
class RegisterView(View):
    def get(self, request):
        return render(request, 'register.html')

    def post(self, request):
        '''进行注册处理'''
        # 接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        # 进行数据校验
        if not all([username, password, email]):
            # 数据不完整
            return render(request, 'register.html', {'errormsg': '数据不完整'})
        # 校验邮箱
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errormsg': '邮箱格式不正确'})
        if allow != 'on':
            return render(request, 'register.html', {'errormsg': '请同意协议'})
        try:
            # 判断数据库中是否有这个用户
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # 如果抛出异常，说明用户不存在，也就是该用户是可用的
            user = None
        # 进行业务处理：进行用户注册
        if user:
            return render(request, 'register.html', {'errormsg': '用户名已存在'})
        user = User.objects.create_user(username, email, password)
        user.is_active = 0
        user.save()
        # 对user_id进行加密
        user_id = user.id
        info = {'confirm': user_id}
        secret = TimedJSONWebSignatureSerializer(settings.SECRET_KEY, 3600)
        res = secret.dumps(info)
        res = res.decode('utf8')
        # 发送邮件
        tasks.send_register_active_email.delay(email, username, res)
        # 返回应答,跳转到首页
        return redirect(reverse('goods:index'))

class ActiveView(View):
    '''激活类视图'''
    def get(self, request, token):
        secret = TimedJSONWebSignatureSerializer(settings.SECRET_KEY, 3600)
        try:
            info = secret.loads(token)
            user_id = info['confirm']
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            return HttpResponse('激活链接已过期')

class LoginView(View):
    '''登录类视图'''
    def get(self, request):
        # 判断用户是否记住用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES['username']
            checked = 'checked'
        else:
            username = ''
            checked = ''
        return render(request, 'login.html', {'username': username, 'checked': checked})

    def post(self, request):
        '''登录校验'''
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        if not all([username, password]):
            return render(request, 'login.html', {'errormsg': '数据不完整'})
        # 使用django自带的认证系统,如果账号密码都正确，那么返回一个user对象，否则返回一个None
        user = authenticate(username=username, password=password)
        if user is not None:
            # 用户存在
            # 判断用户是否激活
            if user.is_active:
                # 用户已激活
                # 记录用户的登录状态
                login(request ,user)
                # 获取用户登陆后所要跳转的地址,如果获取不到next值，也就是获取不到跳转的地址，那么就跳转回首页
                next_url = request.GET.get('next', reverse('goods:index'))
                response = redirect(next_url)
                # 判断用户是否记住用户名
                remember = request.POST.get('remember')
                if remember == 'on':
                    # 记住用户名
                    response.set_cookie('username', username, max_age=7*24*3600)
                else:
                    # 不记住用户名
                    response.delete_cookie('username')
                return response
            else:
                # 用户未激活
                return render(request, 'login.html', {'errormsg': '用户未激活'})
        else:
            # 用户不存在
            return render(request, 'login.html', {'errormsg': '用户名或密码错误'})

class LogoutView(View):
    '''退出登录'''
    def get(self, request):
        # 清除用户的session信息
        logout(request)
        # 跳转到首页
        return redirect(reverse('goods:index'))

class UserInfoView(LoginRequiredMixin, View):
    '''用户中心-信息页'''
    def get(self, request):
        # request.user
        # request.user.is_authenticated()
        # 如果用户未登录->AnnoymousUser的一个实例
        # 如果用户登录->Use类的一个实例
        # 在渲染模板的过程中，除了你给模板文件传递的模板变量之外，django框架会把request.user也传给模板文件
        # 获取用户的个人信息
        user = request.user
        address = Address.objects.get_default_address(user)
        # 获取用户的历史浏览记录
        # 使用django-redis所带的redis后端缓存
        history_key = 'history_%s' % (user.id)
        con = get_redis_connection('default')
        # 读取五条浏览记录
        sku_ids = con.lrange(history_key, 0, 4)
        # 如果直接对sku_ids进行数据库查询的话，那么数据库是不会根据先后来进行排列的,如下面一行代码，因此需要人为的进行排列
        # goods_li = GoodsSKU.objects.filter(id__in=sku_ids)
        goods_li = []
        for sku_id in sku_ids:
            goods = GoodsSKU.objects.get(id=sku_id)
            goods_li.append(goods)
        # 组织上下文
        context = {'page':'user', 'address':address, 'goods_li':goods_li}
        return render(request, 'user_center_info.html', context)

class UserOrderView(LoginRequiredMixin, View):
    '''用户中心-订单页'''
    def get(self, request, page):
        # 获取用户订单信息
        user = request.user
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')
        # 遍历获取订单商品的信息
        for order in orders:
            order_skus = OrderGoods.objects.filter(order_id=order.order_id)
            # 遍历order_skus计算商品小计
            for order_sku in order_skus:
                # 计算商品小计
                amount = order_sku.count * order_sku.price
                # 动态保存商品小计
                order_sku.amount = amount
            # 动态给order增加属性，保存订单商品的状态信息
            order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
            # 动态给order增加属性，保存订单商品的信息
            order.order_skus = order_skus

        # 分页
        paginator = Paginator(orders, 1)

        # 获取第page页的内容，由于页码也是通过url传过来的，用户也是可以随便写的，因此要对page进行容错处理
        try:
            page = int(page)
        except Exception as e:
            # 如果用户页码传入错误，那么默认显示第一页
            page = 1
        if page > paginator.num_pages:
            # 用户传入的页码超过实际页数页默认显示第一页
            page = 1
        # 获取第page页的Page实例对象
        order_page = paginator.page(page)
        # tudo: 进行页码控制，页面上最多显示5个页码
        # 总页数小于5页，页面上显示所有页码
        # 如果当前页是前三页，显示1-5页
        # 如果当前页是后三页，显示后5页
        # 其它情况，显示当前页的前两页和当前页以及后两页
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif (num_pages - page) <= 2:
            pages = (num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        # 组织上下文
        context = {
            'order_page': order_page,
            'pages': pages,
            'page': 'order'
        }

        return render(request, 'user_center_order.html', context)

class UserAddressView(LoginRequiredMixin, View):
    '''用户中心-地址页'''
    def get(self, request):
        user = request.user
        # 判断用户是否有默认收货地址，如果有，则返回对应的一个对象，如果没有，则报错
        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     # 不存在默认收货地址
        #     address = None
        # 使用自定义模型管理器
        address = Address.objects.get_default_address(user)

        return render(request, 'user_center_site.html', {'page':'address', 'address':address})

    def post(self, request):
        '''地址添加'''
        # 接收数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')
        # 判断数据完整性
        if not all([receiver, addr, phone]):
            return render(request, 'user_center_site.html', {'errormsg': '数据不完整'})
        # 检验手机号
        if not re.match(r'^1[3|4|5|7|8]{9}$', phone):
            return render(request, 'user_center_site.html', {'errormsg':'手机格式不正确'})
        # 地址添加
        # 如果用户已存在默认添加地址，添加的地址不作为默认收货地址，否则作为默认收货地址
        # 获取登录用户对应的user对象
        user = request.user
        # 判断用户是否有默认收货地址，如果有，则返回对应的一个对象，如果没有，则报错
        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     # 不存在默认收货地址
        #     address = None
        # 使用自定义模型管理器
        address = Address.objects.get_default_address(user)

        if address:
            # 用户存在默认收货地址
            is_default = False
        else:
            # 用户不存在默认收货地址
            is_default = True
        # 添加地址
        Address.objects.create(user=user,
                               receiver=receiver,
                               addr=addr,
                               zip_code=zip_code,
                               phone=phone,
                               is_default=is_default)
        # 返回应答,刷新地址页面
        return redirect(reverse('user:address'))    # 重定向redirect默认是get请求