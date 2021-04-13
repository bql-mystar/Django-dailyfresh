from django.urls import path
from apps.goods.views import IndexView, DetailView, ListView

urlpatterns = [
    path('index', IndexView.as_view(), name='index'),   # 首页
    # path('', IndexView.as_view(), name='index'),    # 首页
    path('goods_<goods_id>', DetailView.as_view(), name='detail'),  # 详情页
    path('list/<type_id>/<page>', ListView.as_view(), name='list'),     # 列表页

]
