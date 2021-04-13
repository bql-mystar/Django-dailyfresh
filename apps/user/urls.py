from django.urls import path
from apps.user import views
from apps.user.views import RegisterView, ActiveView, LoginView, UserInfoView, UserOrderView, UserAddressView, LogoutView
from django.contrib.auth.decorators import login_required

urlpatterns = [
    # path('register', views.register, name='register'),
    # path('register_handle', views.register_handle, name='register_handle'),
    path('register', RegisterView.as_view(), name='register'),  # 注册
    path('active/<token>', ActiveView.as_view(), name='active'),    # 用户激活
    path('login', LoginView.as_view(), name='login'),   # 登录
    # path('', login_required(UserInfoView.as_view()), name='user'),  # 用户信息-信息页
    # path('order', login_required(UserOrderView.as_view()), name='order'),   # 用户中心-订单页
    # path('address', login_required(UserAddressView.as_view()), name='address'), # 用户中心-地址页
    path('', UserInfoView.as_view(), name='user'),  # 用户信息-信息页
    path('order/<page>', UserOrderView.as_view(), name='order'),   # 用户中心-订单页
    path('address', UserAddressView.as_view(), name='address'), # 用户中心-地址页
    path('logout', LogoutView.as_view(), name='logout'),    # 注销登录
]
