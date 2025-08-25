import pandas as pd
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from django.core.files.storage import FileSystemStorage
import os
from django.conf import settings
from .models import EmployeeData, AOPTarget, AppUser
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO
from django.http import FileResponse
from .serializers import AOPTargetSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import AllowAny
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from io import BytesIO
from datetime import datetime

ROLE_HIERARCHY = {
    'DM': ['DM', 'AM', 'Seller'],
    'AM': ['AM', 'Seller'],
    'Seller': ['Seller'],
}

def filter_data_by_user_role(df, user):
    # Normalize Emp IDs in dataframe to string and strip whitespace
    df['Emp ID'] = df['Emp ID'].astype(str).str.strip()

    # Get unique Emp IDs after normalization
    emp_ids = df['Emp ID'].unique().tolist()

    # Query AppUser and normalize employee IDs keys similarly
    app_user_qs = AppUser.objects.filter(employee_id__in=emp_ids).values('employee_id', 'position')
    emp_position_map = {str(u['employee_id']).strip(): u['position'] for u in app_user_qs}

    # Map positions without defaulting to 'Seller' here
    df.loc[:, 'Position'] = df['Emp ID'].map(emp_position_map)

    # Log unmapped Emp IDs for debugging
    unmapped = df[df['Position'].isna()]['Emp ID'].unique()
    if len(unmapped) > 0:
        print(f"Warning: Emp IDs with no position mapping: {unmapped}")

    # Fill missing positions with a neutral value or leave as NaN
    df['Position'] = df['Position'].fillna('Unknown')

    # Filter by user region (case-insensitive)
    if user.region:
        df = df[df['Region'].astype(str).str.strip().str.lower() == user.region.lower().strip()]

    # Filter by allowed roles in the hierarchy
    allowed_positions = ROLE_HIERARCHY.get(user.position, [])
    df = df[df['Position'].isin(allowed_positions)]

    # If user is Seller, restrict further to own Emp ID
    if user.position == 'Seller':
        df = df[df['Emp ID'] == str(user.employee_id).strip()]

    return df


def get_consolidated_data():
    """
    Reads and consolidates active Excel files into one DataFrame,
    keeping latest record per Emp ID.
    No filtering done here; filtering to be done separately.
    """
    active_files = EmployeeData.objects.filter(is_active=True).order_by('-uploaded_at')
    dfs = []
    for record in active_files:
        try:
            file_path = os.path.normpath(os.path.join(settings.MEDIA_ROOT, record.excel_file.name))
            if os.path.exists(file_path):
                df = pd.read_excel(file_path)
                df['_uploaded_at'] = record.uploaded_at
                dfs.append(df)
        except Exception as e:
            print(f"Error reading file {record.excel_file.name}: {e}")
            continue

    if dfs:
        consolidated_df = (
            pd.concat(dfs)
            .sort_values('_uploaded_at', ascending=False)
            .drop_duplicates(subset=['Emp ID'], keep='first')
            .drop(columns=['_uploaded_at'])
        )
        return consolidated_df
    return pd.DataFrame()

class UploadExcelView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if 'file' not in request.FILES:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)
        uploaded_file = request.FILES['file']
        if not uploaded_file.name.endswith('.xlsx'):
            return Response({"error": "Invalid file type. Only .xlsx allowed"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'uploads'))
            EmployeeData.objects.filter(excel_file__endswith=uploaded_file.name).update(is_active=False)
            filename = fs.save(uploaded_file.name, uploaded_file)
            file_path = os.path.join(settings.MEDIA_ROOT, 'uploads', filename)
            df = pd.read_excel(file_path)
            EXPECTED_COLUMNS = ["Emp ID", "Emp Name", "Region", "Revenue", "GP", "SIP Payout Amount", "Approval", "SIP Paid"]
            if not all(col in df.columns for col in EXPECTED_COLUMNS):
                fs.delete(filename)
                return Response({"error": f"Missing columns. Expected: {EXPECTED_COLUMNS}"}, status=status.HTTP_400_BAD_REQUEST)
            EmployeeData.objects.create(
                excel_file=os.path.join('uploads', filename),
                is_active=True
            )
            consolidated_df = get_consolidated_data()
            filtered_df = filter_data_by_user_role(consolidated_df, request.user)
            return Response({
                "success": True,
                "message": "File processed successfully",
                "employee_count": filtered_df.shape[0]
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LatestFileView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        latest_file = EmployeeData.objects.filter(is_active=True).order_by('-uploaded_at').first()
        if not latest_file:
            return Response({"error": "No files uploaded yet"}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            "filename": os.path.basename(latest_file.excel_file.name),
            "uploaded_at": latest_file.uploaded_at
        })

class RawDataView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            df = get_consolidated_data()
            if df.empty:
                return Response({"error": "No active data available"}, status=status.HTTP_404_NOT_FOUND)
            filtered_df = filter_data_by_user_role(df, user)
            if filtered_df.empty:
                return Response({"error": "No data available for your permissions"}, status=status.HTTP_404_NOT_FOUND)
            totals = {
                "Revenue": filtered_df["Revenue"].sum(),
                "GP": filtered_df["GP"].sum(),
                "SIP Payout Amount": filtered_df["SIP Payout Amount"].sum()
            }
            return Response({
                "data": filtered_df.to_dict('records'),
                "totals": totals
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SummaryView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            df = get_consolidated_data()
            if df.empty:
                return Response({"error": "No active data available"}, status=status.HTTP_404_NOT_FOUND)
            filtered_df = filter_data_by_user_role(df, user)
            if filtered_df.empty:
                return Response({"error": "No data available for your permissions"}, status=status.HTTP_404_NOT_FOUND)

            paid_rows = filtered_df[filtered_df["SIP Paid"] == "Yes"]
            pending = filtered_df[filtered_df["Approval"] == "Not yet"].shape[0]
            total_rows = filtered_df.shape[0]
            success_rate = round((paid_rows.shape[0] / total_rows) * 100, 2) if total_rows > 0 else 0

            return Response({
                "paid_total": paid_rows["SIP Payout Amount"].sum(),
                "pending_approvals": pending,
                "success_rate": success_rate
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GeneratePDFView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, emp_id):
        try:
            user = request.user
            df = get_consolidated_data()
            if df.empty:
                return Response({"error": "No active data available"}, status=status.HTTP_404_NOT_FOUND)
            filtered_df = filter_data_by_user_role(df, user)
            if filtered_df.empty:
                return Response({"error": "Access denied or data not found"}, status=status.HTTP_403_FORBIDDEN)

            try:
                employee = filtered_df[filtered_df["Emp ID"] == emp_id].iloc[0]
            except (IndexError, ValueError):
                return Response({"error": "Invalid Employee ID or Access denied"}, status=status.HTTP_404_NOT_FOUND)

            buffer = BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter

            # Margins
            margin = inch  # 72 points = 1 inch

            # Title
            p.setFont("Helvetica-Bold", 18)
            p.drawCentredString(width / 2, height - margin + 10, "EMPLOYEE SIP PAYOUT SLIP")

            # Separator line below title
            p.setStrokeColor(colors.grey)
            p.setLineWidth(1)
            p.line(margin, height - margin, width - margin, height - margin)

            # Employee info table data (label and value pairs)
            data = [
                ['Employee ID:', str(employee["Emp ID"])],
                ['Name:', employee.get("Emp Name", "")],
                ['Position:', employee.get("Position", "N/A")],
                ['Region:', employee.get("Region", "")],
                ['SIP Payout Amount:', f"${employee['SIP Payout Amount']:,.2f}"],
            ]

            # Create table with 2 columns: label and value
            table = Table(data, colWidths=[2*inch, width - 2*margin - 2*inch])
            style = TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('ALIGN', (0, 0), (0, -1), 'RIGHT'),  # Right align labels
                ('ALIGN', (1, 0), (1, -1), 'LEFT'),   # Left align values
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
            ])
            table.setStyle(style)

            # Position table on the page below the title
            table_width, table_height = table.wrap(0, 0)
            table.drawOn(p, margin, height - margin - 30 - table_height)

            # Footer with generation date and page number
            p.setFont("Helvetica-Oblique", 8)
            p.setFillColor(colors.grey)
            footer_text = f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            p.drawString(margin, margin / 2, footer_text)
            p.drawRightString(width - margin, margin / 2, "Page 1")

            p.showPage()
            p.save()
            buffer.seek(0)

            return FileResponse(buffer, as_attachment=True, filename=f"sip_slip_{emp_id}.pdf", content_type='application/pdf')

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AOPTargetUploadView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if 'file' not in request.FILES:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)
        excel_file = request.FILES['file']
        if not excel_file.name.endswith('.xlsx'):
            return Response({"error": "Only '.xlsx' files allowed"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'aop_uploads'))
            filename = fs.save(excel_file.name, excel_file)
            file_path = os.path.join(settings.MEDIA_ROOT, 'aop_uploads', filename)
            expected_cols = ['ShipTo', 'PY Actuals', 'Growth%', 'Region', 'Emp ID']
            df = pd.read_excel(file_path)
            if not all(col in df.columns for col in expected_cols):
                fs.delete(filename)
                return Response({"error": f"Excel must contain columns: {expected_cols}"}, status=status.HTTP_400_BAD_REQUEST)
            AOPTarget.objects.all().delete()
            objs = []
            for _, row in df.iterrows():
                py_actuals = row['PY Actuals']
                growth_percent = row['Growth%'] if not pd.isna(row['Growth%']) else 0
                target = py_actuals * (1 + growth_percent / 100)
                obj = AOPTarget(
                    ship_to=row['ShipTo'],
                    py_actuals=py_actuals,
                    growth_percent=growth_percent,
                    target=target,
                    region=row['Region'],
                    emp_id=str(row['Emp ID']).strip() if 'Emp ID' in row else None
                )
                objs.append(obj)
            AOPTarget.objects.bulk_create(objs)
            fs.delete(filename)
            return Response({"success": True, "message": "File uploaded and data saved."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AOPTargetListView(generics.ListAPIView):
    serializer_class = AOPTargetSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = AOPTarget.objects.all()
        if user.position in ['DM', 'AM']:
            qs = qs.filter(region=user.region)
        elif user.position == 'Seller':
            qs = qs.filter(emp_id=user.employee_id)
        else:
            qs = qs.none()
        return qs

class AOPTargetUpdateView(generics.UpdateAPIView):
    queryset = AOPTarget.objects.all()
    serializer_class = AOPTargetSerializer
    lookup_field = 'id'
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.position in ['DM', 'AM']:
            qs = qs.filter(region=user.region)
        elif user.position == 'Seller':
            qs = qs.filter(emp_id=user.employee_id)
        else:
            qs = qs.none()
        return qs


class AccessFileUploadView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if 'file' not in request.FILES:
            return Response({"error": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)
        excel_file = request.FILES['file']
        if not excel_file.name.endswith('.xlsx'):
            return Response({"error": "Only '.xlsx' files allowed"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'access_uploads'))
            filename = fs.save(excel_file.name, excel_file)
            file_path = os.path.join(settings.MEDIA_ROOT, 'access_uploads', filename)
            df = pd.read_excel(file_path)
            expected_cols = ['Position', 'Name', 'Employee ID', 'Password', 'Region']
            if not all(col in df.columns for col in expected_cols):
                fs.delete(filename)
                return Response({"error": f"Excel must contain columns: {expected_cols}"}, status=status.HTTP_400_BAD_REQUEST)
            for _, row in df.iterrows():
                employee_id = str(row['Employee ID']).strip()
                position = str(row['Position']).strip()
                name = row['Name']
                password = str(row['Password'])
                region = row['Region']
                if position not in ['DM', 'AM', 'Seller']:
                    continue
                user, _ = AppUser.objects.get_or_create(employee_id=employee_id)
                user.name = name
                user.position = position
                user.region = region
                user.set_password(password)
                user.save()
            fs.delete(filename)
            return Response({"success": True, "message": "User access data uploaded successfully"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        employee_id = request.data.get('employee_id')
        password = request.data.get('password')
        if not employee_id or not password:
            return Response({"error": "Employee ID and password required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = AppUser.objects.get(employee_id=employee_id)
        except AppUser.DoesNotExist:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.check_password(password):
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'employee_id': user.employee_id,
                'name': user.name,
                'position': user.position,
                'region': user.region,
            }
        })
