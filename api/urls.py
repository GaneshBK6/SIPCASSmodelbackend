from django.urls import path
from .views import UploadExcelView, RawDataView, SummaryView, GeneratePDFView, LatestFileView

urlpatterns = [
    path('upload/', UploadExcelView.as_view(), name='upload'),
    path('raw-data/', RawDataView.as_view(), name='raw-data'),
    path('summary/', SummaryView.as_view(), name='summary'),
    path('pdf/<str:emp_id>/', GeneratePDFView.as_view(), name='generate-pdf'),
    path('latest-file/', LatestFileView.as_view(), name='latest-file'),
]