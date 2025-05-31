import pandas as pd
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.files.storage import FileSystemStorage
import os
from django.conf import settings
from .models import EmployeeData # Assuming you have this model defined
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
from django.http import FileResponse

def get_consolidated_data(region=None):
    """
    Returns DataFrame combining all active uploads,
    optionally filtered by region.
    Prioritizes files by upload time (newest wins for duplicate Emp IDs).
    """
    # Get active files sorted by upload time (newest first)
    active_files = EmployeeData.objects.filter(is_active=True).order_by('-uploaded_at')
    
    dfs = []
    for record in active_files:
        try:
            file_path = os.path.normpath(os.path.join(settings.MEDIA_ROOT, record.excel_file.name))
            if os.path.exists(file_path):
                df = pd.read_excel(file_path)
                # Add upload timestamp to track file priority
                df['_uploaded_at'] = record.uploaded_at
                dfs.append(df)
        except Exception as e:
            print(f"Error reading file {record.excel_file.name}: {e}")
            continue
            
    if dfs:
        # Combine and keep last uploaded entry for each Emp ID
        consolidated_df = (
            pd.concat(dfs)
            .sort_values('_uploaded_at', ascending=False)  # Newest files first
            .drop_duplicates(subset=['Emp ID'], keep='first')  # Keep first occurrence (newest)
            .drop(columns=['_uploaded_at'])  # Remove temporary column
        )
        
        # Apply region filter if provided
        if region and region.lower() != 'all':
            if 'Region' in consolidated_df.columns:
                consolidated_df = consolidated_df[
                    consolidated_df['Region'].astype(str).str.lower() == region.lower()
                ]
            else:
                print("Warning: 'Region' column not found in data for filtering.")
        
        return consolidated_df
    
    return pd.DataFrame()

class UploadExcelView(APIView):
    def post(self, request):
        if 'file' not in request.FILES:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)
        
        uploaded_file = request.FILES['file']
        if not uploaded_file.name.endswith('.xlsx'):
            return Response({"error": "Invalid file type. Only .xlsx allowed"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'uploads'))
            
            # Deactivate previous version if same filename exists
            # This assumes filename is unique enough or you want to deactivate based on full name
            EmployeeData.objects.filter(
                excel_file__endswith=uploaded_file.name
            ).update(is_active=False)
            
            # Save new file
            filename = fs.save(uploaded_file.name, uploaded_file)
            file_path = os.path.join(settings.MEDIA_ROOT, 'uploads', filename)
            
            # Validate Excel structure
            df = pd.read_excel(file_path)
            EXPECTED_COLUMNS = [
                "Emp ID", "Emp Name", "Region", "Revenue", "GP", 
                "SIP Payout Amount", "Approval", "SIP Paid"
            ]
            if not all(col in df.columns for col in EXPECTED_COLUMNS):
                fs.delete(filename)
                return Response({"error": f"Missing columns. Expected: {EXPECTED_COLUMNS}"}, 
                                status=status.HTTP_400_BAD_REQUEST)
            
            # Store new file record
            EmployeeData.objects.create(
                excel_file=os.path.join('uploads', filename),
                is_active=True
            )
            
            return Response({
                "success": True,
                "message": "File processed successfully",
                "employee_count": get_consolidated_data().shape[0]
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LatestFileView(APIView):
    def get(self, request):
        latest_file = EmployeeData.objects.filter(is_active=True).order_by('-uploaded_at').first()
        if not latest_file:
            return Response({"error": "No files uploaded yet"}, status=status.HTTP_404_NOT_FOUND)
        
        return Response({
            "filename": os.path.basename(latest_file.excel_file.name),
            "uploaded_at": latest_file.uploaded_at
        })

class RawDataView(APIView):
    def get(self, request):
        try:
            # Get region from query parameters
            region = request.query_params.get('region')
            df = get_consolidated_data(region=region) # Pass region to the function

            if df.empty:
                return Response({"error": "No active data available for this region or overall"}, status=status.HTTP_404_NOT_FOUND)
            
            return Response({
                "data": df.to_dict('records'),
                "totals": {
                    "Revenue": df["Revenue"].sum(),
                    "GP": df["GP"].sum(),
                    "SIP Payout Amount": df["SIP Payout Amount"].sum()
                }
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SummaryView(APIView):
    def get(self, request):
        try:
            # Get region from query parameters
            region = request.query_params.get('region')
            df = get_consolidated_data(region=region) # Pass region to the function

            if df.empty:
                return Response({"error": "No active data available for this region or overall"}, status=status.HTTP_404_NOT_FOUND)
            
            paid_rows = df[df["SIP Paid"] == "Yes"]
            pending = df[df["Approval"] == "Not yet"].shape[0]
            
            # Calculate success rate safely to avoid division by zero
            total_rows = df.shape[0]
            success_rate = round((paid_rows.shape[0] / total_rows) * 100, 2) if total_rows > 0 else 0
            
            return Response({
                "paid_total": paid_rows["SIP Payout Amount"].sum(),
                "pending_approvals": pending,
                "success_rate": success_rate # Use the safely calculated rate
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GeneratePDFView(APIView):
    def get(self, request, emp_id):
        try:
            df = get_consolidated_data()
            if df.empty:
                return Response({"error": "No active data available"}, status=status.HTTP_404_NOT_FOUND)
            
            try:
                employee = df[df["Emp ID"] == int(emp_id)].iloc[0]
            except (IndexError, ValueError):
                return Response({"error": "Invalid Employee ID"}, status=status.HTTP_404_NOT_FOUND)
            
            buffer = BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)
            
            # PDF Content
            p.setFont("Helvetica-Bold", 14)
            p.drawString(100, 750, "EMPLOYEE SIP PAYOUT SLIP")
            p.setFont("Helvetica", 12)
            p.drawString(100, 700, f"Emp ID: {employee['Emp ID']}")
            p.drawString(100, 670, f"Name: {employee['Emp Name']}")
            p.drawString(100, 640, f"Region: {employee['Region']}")
            p.drawString(100, 610, f"SIP Amount: ${employee['SIP Payout Amount']:,.2f}")
            
            p.showPage()
            p.save()
            buffer.seek(0)
            
            return FileResponse(
                buffer,
                as_attachment=True,
                filename=f"sip_slip_{emp_id}.pdf",
                content_type='application/pdf'
            )
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


