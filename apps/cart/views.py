from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import JsonResponse
from django.views.generic import View
from apps.goods.models import GoodsSKU
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin

# Create your views here.
class CartAddView(View):
    '''购物车记录添加'''
    def post(self, request):
        '''购物车记录添加'''
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({'res':-1, 'errmsg': '请登录'})
        # 接收数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')
        # 校验数据
        if not all([sku_id, count]):
            return  JsonResponse({'res':0, 'errmsg': '数据不完整'})
        # 校验添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            # 数目出错
            return JsonResponse({'res':1, 'errmsg': '商品数目出错'})

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            # 商品不存在
            return JsonResponse({'res':2, 'errmsg': '商品不存在'})

        # 业务处理：添加购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%s' % user.id
        # 尝试获取sku_id对应redis数据库中购物车数据
        # hget方法：如果sku_id在hash中不存在，不会报错，而是返回一个None
        cart_count = conn.hget(cart_key, sku_id)
        if cart_count:
            # 说明原来的购物车中已经含有该商品，因此要在该商品原有的数目上添加现有添加购物车的数量
            count += int(cart_count)        # 从reids中读取到的内容均为字符串

        # 判断购物车的数目和商品库存
        if count > sku.stock:
            return JsonResponse({'res':3, 'errmsg':'商品库存不足'})

        # 设置hash中sku_id的值
        # hset方法：如果对应的内容不存在的话就是新增，如果存在的话就是更新
        conn.hset(cart_key, sku_id, count)

        # 计算用户购物车中商品的条目数
        total_count = conn.hlen(cart_key)

        # 返回应答
        return JsonResponse({'res': 4, 'total_count': total_count, 'message': '添加成功'})

class CartInfoView(LoginRequiredMixin, View):
    '''购物车页面显示'''
    def get(self, request):
        '''显示购物车页面'''
        # 获取用户购物车中商品的信息
        user = request.user
        conn = get_redis_connection('default')
        cart_key = 'cart_%s' % user.id
        # hgetall返回的是一个python的字典，其内容就是redis中对应的内容，格式如下：{'商品id'：'商品数目'}
        cart_dict = conn.hgetall(cart_key)
        skus = []
        # 保存用户购物车中商品的总数目和总价格
        total_count = 0
        total_price = 0
        # 遍历获取商品的信息
        for sku_id, count in cart_dict.items():
            # 根据商品的id获取商品的信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 计算商品小计
            amount = sku.price * int(count)
            # 动态给sku对象一个amount属性，保存商品小计
            sku.amount = amount
            # 动态给sku对象一个count属性，保存购物车中对应商品的数量
            sku.count = int(count)
            skus.append(sku)
            # 累加计算商品总数目和总价格
            total_count += int(count)
            total_price += amount

        # 组织模板上下文
        context = {
            'total_count': total_count,
            'total_price': total_price,
            'skus': skus
        }

        return render(request, 'cart.html', context)

class CartUpdateView(View):
    '''购物车记录更新'''
    def post(self, request):
        '''购物车记录更新'''
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({'res': -1, 'errmsg': '请登录'})
        # 接收数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')
        # 校验数据
        if not all([sku_id, count]):
            return JsonResponse({'res': 0, 'errmsg': '数据不完整'})
        # 校验添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            # 数目出错
            return JsonResponse({'res': 1, 'errmsg': '商品数目出错'})

        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            # 商品不存在
            return JsonResponse({'res': 2, 'errmsg': '商品不存在'})

        # 业务处理：更新购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%s' % user.id
        if count > sku.stock:
            # 添加购物车数量超过库存数目
            return JsonResponse({'res': 3, 'errormsg': '库存不足'})
        # 更新
        conn.hset(cart_key, sku_id, count)
        # 计算用户购物车中商品总件数
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)
        # 返回应答
        return JsonResponse({'res': 4, 'message': '更新成功', 'total_count': total_count})

class CartDeleteView(View):
    '''购物车记录删除'''
    def post(self, request):
        '''购物车记录删除'''
        user = request.user
        if not user.is_authenticated:
            # 用户未登录
            return JsonResponse({'res': 0, 'errmsg': '请登录'})
        # 接收数据
        sku_id = request.POST.get('sku_id')
        # 数据校验
        if not sku_id:
            return JsonResponse({'res':1, 'errormsg':'无效的商品id'})
        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res':2, 'errormsg':'商品不存在'})
        # 业务处理
        conn = get_redis_connection('default')
        cart_key = 'cart_%s' % user.id
        conn.hdel(cart_key, sku_id)
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)
        # 返回应答
        return JsonResponse({'res':3, 'message':'删除成功', 'total_count':total_count})