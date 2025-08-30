from django.shortcuts import render
from core.middleware import skip_permission

# Create your views here.
@skip_permission
def dashboard(request):
    context = { 'title' : 'Dashboard' }
    return render(request, 'frontend/dashboard.html', context)
