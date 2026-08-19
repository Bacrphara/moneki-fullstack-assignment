from django.contrib import admin
from django.urls import path

from analytics import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.dashboard, name="dashboard"),
    path("health/", views.health, name="health"),
    path("api/dashboard/summary", views.summary_api),
    path("api/dashboard/trend", views.trend_api),
    path("api/dashboard/top-products", views.top_products_api),
    path("api/dashboard/store-comparison", views.store_comparison_api),
]
