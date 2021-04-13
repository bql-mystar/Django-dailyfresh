from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic import View
from apps.goods.models import GoodsType, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner, GoodsSKU
from apps.order.models import OrderGoods
from django_redis import get_redis_connection
from django.core.cache import cache
from django.core.paginator import Paginator

# Create your views here.
class IndexView(View):
    '''首页'''
    def get(self, request):
        '''显示首页'''
        # 先从缓存中获取数据，如果没有数据，那么返回None
        context = cache.get('index_page_data')
        if context is None:
            # 缓存中无数据，从数据库中读取数据，并设置缓存
            print('设置缓存')
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
            context = {
                'types': types,
                'goods_banner': goods_banner,
                'promotion_banners': promotion_banners
            }
            cache.set('index_page_data', context, 3600)
        # 获取用户购物车中商品数目
        cart_count = 0
        # 判断用户是否登录，如果登录，就从redis缓存中读取购物车中商品数量，如果未登录，则默认为0
        user = request.user
        if user.is_authenticated:
            # 用户登录
            conn = get_redis_connection('default')
            # 用户的购物车格式为 cart_id
            cart_key = 'cart_%d' % (user.id)
            cart_count = conn.hlen(cart_key)
        # 组织模板上下文
        # 字典有一个updata方法，如果key对应的值不存在就是添加，如果存在就是更新
        context.update(cart_count=cart_count)
        return render(request, 'index.html', context)

class DetailView(View):
    '''详情页'''
    def get(self, request, goods_id):
        '''显示详情页'''
        try:
            sku = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist:
            # 商品不存在
            return redirect(reverse('goods:index'))
        # 获取商品的分类信息
        types = GoodsType.objects.all()
        # 获取商品的评论信息,使用exclude来将空评论排除
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment='')
        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2]
        # 获取同一个SPU的其它规格商品
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id)
        # 获取用户购物车中商品数目
        cart_count = 0
        # 判断用户是否登录，如果登录，就从redis缓存中读取购物车中商品数量，如果未登录，则默认为0
        user = request.user
        if user.is_authenticated:
            # 用户登录
            conn = get_redis_connection('default')
            # 用户的购物车格式为 cart_id
            cart_key = 'cart_%d' % (user.id)
            cart_count = conn.hlen(cart_key)
            # 添加用户的历史浏览记录
            history_key = 'history_%s' % user.id
            # 移除列表中的goods_id,lrem的用法就是如果列表中存在数据就删除，如果不存在就不作为
            conn.lrem(history_key, 0, goods_id)
            # 把goods_id插入到列表左侧
            conn.lpush(history_key, goods_id)
            # 根据需求可以设置对应的历史记录长度，假设只保存五条,ltrim的作用就是只保留区间内的数据
            conn.ltrim(history_key, 0, 4)
        # 组织模板上下文
        context = {
            'sku': sku,
            'types': types,
            'sku_orders': sku_orders,
            'new_skus': new_skus,
            'same_spu_skus': same_spu_skus,
            'cart_count': cart_count
        }
        return render(request, 'detail.html', context)
    
class ListView(View):
    '''列表页'''
    def get(self, request, type_id, page):
        try:
            # 先获取种类信息，url地址是可以用户自己进行选择浏览的，因此用户浏览的种类id可能会大于数据库中最大的种类id，因此要进行容错配置
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            # 种类不存在
            return redirect(reverse('goods:index'))
        # 获取商品的分类信息
        types = GoodsType.objects.all()
        # 获取排序的方式,获取分类商品的信息
        sort = request.GET.get('sort')
        # sort=default,按照默认id排序
        # sort=price,按照商品价格排序
        # sort=hot,按照商品的销量排序
        if sort == 'price':
            skus = GoodsSKU.objects.filter(type=type).order_by('price')
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type).order_by('-sales')
        else:
            sort = 'default'
            skus = GoodsSKU.objects.filter(type=type).order_by('-id')
        # 对数据进行分页
        paginator = Paginator(skus, 2)
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
        skus_page = paginator.page(page)
        # tudo: 进行页码控制，页面上最多显示5个页码
        # 总页数小于5页，页面上显示所有页码
        # 如果当前页是前三页，显示1-5页
        # 如果当前页是后三页，显示后5页
        # 其它情况，显示当前页的前两页和当前页以及后两页
        num_pages = paginator.num_pages
        if num_pages<5:
            pages = range(1,num_pages+1)
        elif page<=3:
            pages = range(1,6)
        elif (num_pages-page)<=2:
            pages = (num_pages-4, num_pages+1)
        else:
            pages = range(page-2, page+3)

        # 获取用户购物车中商品数目
        cart_count = 0
        # 判断用户是否登录，如果登录，就从redis缓存中读取购物车中商品数量，如果未登录，则默认为0
        user = request.user
        if user.is_authenticated:
            # 用户登录
            conn = get_redis_connection('default')
            # 用户的购物车格式为 cart_id
            cart_key = 'cart_%d' % (user.id)
            cart_count = conn.hlen(cart_key)
        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2]
        # 组织模板上下文
        context = {
            'type': type,
            'types': types,
            'sort': sort,
            'skus_page': skus_page,
            'new_skus': new_skus,
            'cart_count': cart_count,
            'pages': pages
        }
        return render(request, 'list.html', context)