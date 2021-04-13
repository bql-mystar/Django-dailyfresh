from django.shortcuts import render, redirect
from django.views.generic import View
from django.urls import reverse
from apps.goods.models import GoodsSKU
from apps.user.models import Address
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
from django.http import JsonResponse
from apps.order.models import OrderInfo, OrderGoods
from datetime import datetime
from django.db import transaction
import os
from django.conf import settings
from alipay import AliPay, DCAliPay, ISVAliPay
import time

# Create your views here.
class OrderPlaceView(LoginRequiredMixin, View):
    '''提交订单页面显示'''
    def post(self, request):
        '''提交订单页面显示'''
        # 获取登录的用户
        user = request.user
        # 获取参数
        sku_ids = request.POST.getlist('sku_ids')
        # 校验参数
        if not sku_ids:
            # 跳转到购物车页面
            return redirect(reverse('cart:show'))

        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 遍历sku_ids获取用户要购买的商品信息
        skus = []
        total_count = 0
        total_price = 0
        for sku_id in sku_ids:
            # 根据商品的id获取商品信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 获取用户所要购买商品的数量
            count = conn.hget(cart_key, sku_id)
            # 计算商品小计
            price = sku.price
            amount = price * int(count)
            # 动态给sku添加count和amount，保存购买商品的数量和小计
            sku.count = int(count)
            sku.amount = amount
            skus.append(sku)
            # 累加计算商品的总件数和总价格
            total_count += int(count)
            total_price += amount
        # 运费：实际开发中属于一个子系统
        transmit_price = 10     # 目前没有这个子系统，就直接写死
        # 实付款
        total_pay = total_price + transmit_price
        # 获取用户的收件地址
        adds = Address.objects.filter(user=user)
        sku_ids = ','.join(sku_ids)
        # 组织上下文
        context = {
            'skus': skus,
            'total_count': total_count,
            'total_price': total_price,
            'transmit_price': transmit_price,
            'total_pay': total_pay,
            'addrs': adds,
            'sku_ids': sku_ids
        }
        # 使用模板
        return render(request, 'place_order.html', context)

# 前端传递的参数：地址id：addr_id，支付方式：pay_method，：用户要购买的商品id字符串：sku_ids
class OrderCommitView(View):
    '''订单创建'''
    @transaction.atomic
    def post(self, request):
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({'res':0, 'errmsg':'用户未登录'})
        # 接收参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')
        # print(sku_ids)
        # print(type(sku_ids))
        # return 0
        # 校验参数
        if not all([addr_id, pay_method, sku_ids]):
            # 数据不完整
            return JsonResponse({'res':1, 'errmsg':'参数不完整'})
        # 校验支付方式
        if pay_method not in OrderInfo.PAY_METHOD.keys():
            return JsonResponse({'res':2, 'errmsg':'非法的支付方式'})
        # 校验地址
        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            # 地址不存在
            return JsonResponse({'res':3, 'errmsg':'地址非法'})
        # tudo：创建订单核心业务
        conn = get_redis_connection('default')
        # 组织参数
        # 订单id  订单id格式为 年+月+日+时+分+秒+用户id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        # 运费
        transit_price = 10
        # 总数目和总金额
        total_count = 0
        total_price = 0
        save_id = transaction.savepoint()
        try:
            # tudo: 向df_order_info表中添加一条记录
            order = OrderInfo.objects.create(
                order_id = order_id,
                user = user,
                addr = addr,
                pay_method = pay_method,
                transit_price = transit_price,
                total_count = total_count,
                total_price = total_price
            )
            # tudo: 用户订单中有几个商品，就向df_order_goods表中添加几条记录
            # 将传过来的sku_ids分割成列表
            cart_key = 'cart_%s' % user.id
            sku_ids = sku_ids.split(',')

            for sku_id in sku_ids:
                for i in range(3):
                    # 获取商品的信息
                    try:
                        # 使用悲观锁实现高并发
                        # sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                        # 使用乐观锁实现高并发
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except GoodsSKU.DoesNotExist:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res':4, 'errmsg':'商品不存在'})

                    # 从redis中获取用户所要购买商品的数量
                    count = conn.hget(cart_key, sku_id)

                    # 判断商品库存
                    if int(count) > sku.stock:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res':6, 'errmsg':'商品库存不足'})

                    # tudo: 更新商品的库存和销量(乐观锁)
                    origin_stock = sku.stock
                    new_stock = origin_stock - int(count)
                    new_sales = sku.sales + int(count)

                    # print('user:%d times:%d stock:%d' % (user.id, i, sku.stock))
                    # import time
                    # time.sleep(10)

                    # filter得到一个查询集，查询集里面有个update方法，使用后返回的是受影响的行数
                    res = GoodsSKU.objects.filter(id=sku_id, stock=origin_stock).update(stock=new_stock, sales=new_sales)
                    if res == 0:
                        if i == 2:
                            # 说明没有受影响，也就是说明，该数据已经被别的用户所修改，那么回滚
                            transaction.savepoint_rollback(save_id)
                            return JsonResponse({'res':7, 'errmsg':'下单失败'})
                        continue

                    # tudo：向df_order_goods表中添加一条记录
                    OrderGoods.objects.create(
                        order = order,
                        sku = sku,
                        count = count,
                        price = sku.price
                    )

                    # tudo: 更新商品的库存和销量(悲观锁)
                    # sku.stock -= int(count)
                    # sku.sales += int(count)
                    # sku.save()
                    # tudo:累加计算订单商品的总数目和总价格
                    amount = sku.price * int(count)
                    total_count += int(count)
                    total_price += amount
                    break

            # tudo:更新订单信息表中的总数目和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res':7,'errmsg':'下单失败'})
        # 提交事务
        transaction.savepoint_commit(save_id)
        # tudo：清除用户购物车中对应的记录
        conn.hdel(cart_key, *sku_ids)
        return JsonResponse({'res':5, 'message':'创建成功'})

# 前端传递参数：订单id(order_id)
class OrderPayView(View):
    '''订单支付'''
    def post(self, request):
        '''订单支付'''
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({'res':0, 'errmsg':'用户未登录'})
        # 接收参数
        order_id = request.POST.get('order_id')
        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的订单id'})

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user, pay_method=3, order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单错误'})
        # 业务处理：使用python-alipay-sdk调用支付宝的支付接口
        app_private_key_string = open(os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem')).read()
        alipay_public_key_string = open(os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem')).read()
        # 初始化
        alipay = AliPay(
            appid="2021000118643231",
            app_notify_url=None,  # 默认回调url
            app_private_key_string=app_private_key_string,
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_string=alipay_public_key_string,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug = True  # 默认False
        )
        # 调用支付接口
        # 如果你是 Python 3的用户，使用默认的字符串即可
        subject = "天天生鲜%d" % user.id
        # subject = "赞助下瑧哥呗"
        total_pay = order.total_price + order.transit_price
        # 电脑网站支付，需要跳转到https://openapi.alipay.com/gateway.do? + order_string
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,    # 订单id
            total_amount=str(total_pay),
            subject=subject,
            return_url=None,
            notify_url=None  # 可选, 不填则使用默认notify url
        )
        # 返回应答
        pay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string
        return JsonResponse({'res':3, 'pay_url':pay_url})


class CheckPayView(View):
    def post(self, request):
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
        # 接收参数
        order_id = request.POST.get('order_id')
        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效的订单id'})

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user, pay_method=3, order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单错误'})
        # 业务处理：使用python-alipay-sdk调用支付宝的支付接口
        app_private_key_string = open(os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem')).read()
        alipay_public_key_string = open(os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem')).read()
        # 初始化
        alipay = AliPay(
            appid="2021000118643231",
            app_notify_url=None,  # 默认回调url
            app_private_key_string=app_private_key_string,
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            alipay_public_key_string=alipay_public_key_string,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False
        )
        while True:
            # 调用支付宝的交易接口
            response = alipay.api_alipay_trade_query(order_id)
            code = response.get('code')
            if code == '10000' and response.get('trade_status') == 'TRADE_SUCCESS':
                # 支付成功
                # 获取支付宝交易号
                trade_no = response.get('trade_no')
                # 更新订单状态
                order.trade_no = trade_no
                order.order_status = 4  # 待评价
                order.save()
                # 返回结果
                return  JsonResponse({'res':3, 'message':'支付成功'})
            elif code == '40004' or (code == '10000' and response.get('trade_status') == 'WAIT_BUYER_PAY'):
                # 等待买家付款或者业务处理失败，可能一会就会成功
                time.sleep(5)
                continue
            else:
                # 支付出错
                print(code)
                return JsonResponse({'res':4, 'errmsg':'支付失败'})





