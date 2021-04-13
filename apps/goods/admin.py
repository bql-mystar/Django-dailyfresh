from django.contrib import admin
from apps.goods.models import GoodsType, IndexPromotionBanner, IndexTypeGoodsBanner, IndexGoodsBanner, GoodsSKU, Goods
from celery_tasks import tasks
from django.core.cache import cache

# Register your models here.

class BaseModelAdmin(admin.ModelAdmin):
    '''创建管理类,在后台进行数据变动时，会自动调用save_model或者delete_model方法'''
    def save_model(self, request, obj, form, change):
        '''新增或更新表中的数据时调用'''
        super().save_model(request, obj, form, change)
        # 发出任务，让celery worker重新生成首页静态页
        tasks.generate_static_index_html.delay()
        # 当数据发生变化，那么缓存中的数据也要发生变化，将缓存中对应的数据删除即可，到时候访问对应的网页重新设置缓存就行
        cache.delete('index_page_data')

    def delete_model(self, request, obj):
        '''删除表中的数据时调用'''
        super().delete_model(request, obj)
        # 发出任务，让celery worker重新生成首页静态页
        tasks.generate_static_index_html.delay()
        # 当数据发生变化，那么缓存中的数据也要发生变化，将缓存中对应的数据删除即可，到时候访问对应的网页重新设置缓存就行
        cache.delete('index_page_data')

class IndexPromotionBannerAdmin(BaseModelAdmin):
    pass

class GoodsTypeAdmin(BaseModelAdmin):
    pass

class IndexTypeGoodsBannerAdmin(BaseModelAdmin):
    pass

class IndexGoodsBannerAdmin(BaseModelAdmin):
    pass

class GoodsSkuAdmin(BaseModelAdmin):
    pass

class GoodsAdmin(BaseModelAdmin):
    pass

admin.site.register(GoodsType, GoodsTypeAdmin)
admin.site.register(IndexPromotionBanner, IndexPromotionBannerAdmin)
admin.site.register(IndexGoodsBanner, IndexGoodsBannerAdmin)
admin.site.register(IndexTypeGoodsBanner, IndexPromotionBannerAdmin)
admin.site.register(GoodsSKU, GoodsSkuAdmin)
admin.site.register(Goods, GoodsAdmin)