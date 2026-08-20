from django.contrib import admin
from django.conf import settings
from django.urls import path

from analytics import views

urlpatterns = [
    path(f"{settings.ADMIN_PATH}/", admin.site.urls),
    path("", views.dashboard, name="dashboard"),
    path("health/", views.health, name="health"),
    path("api/dashboard/summary", views.summary_api),
    path("api/dashboard/trend", views.trend_api),
    path("api/dashboard/top-products", views.top_products_api),
    path("api/dashboard/store-comparison", views.store_comparison_api),
    path("api/insights/radar", views.radar_api),
    path("api/assistant/sessions", views.create_session),
    path("api/assistant/chat", views.chat),
    path("api/assistant/sessions/<uuid:session_id>", views.delete_session),
]
