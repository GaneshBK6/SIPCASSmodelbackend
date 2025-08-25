from django.urls import path
from .views import UploadExcelView, RawDataView, SummaryView, GeneratePDFView, LatestFileView, AOPTargetUploadView, AOPTargetListView, AOPTargetUpdateView, AccessFileUploadView, LoginView
from rest_framework_simplejwt.views import TokenRefreshView


urlpatterns = [
    path('upload/', UploadExcelView.as_view(), name='upload'),
    path('raw-data/', RawDataView.as_view(), name='raw-data'),
    path('summary/', SummaryView.as_view(), name='summary'),
    path('pdf/<str:emp_id>/', GeneratePDFView.as_view(), name='generate-pdf'),
    path('latest-file/', LatestFileView.as_view(), name='latest-file'),
    path('aop-targets/upload/', AOPTargetUploadView.as_view(), name='aop-target-upload'),
    path('aop-targets/', AOPTargetListView.as_view(), name='aop-target-list'),
    path('aop-targets/<int:id>/', AOPTargetUpdateView.as_view(), name='aop-target-update'),
    path('access-file/upload/', AccessFileUploadView.as_view(), name='access-file-upload'),
    path('login/', LoginView.as_view(), name='login'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('create-superuser/', CreateSuperuserView.as_view(), name='create-superuser'),
]