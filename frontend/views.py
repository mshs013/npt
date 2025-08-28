from django.shortcuts import render

# Create your views here.

def dashboard(request):
    context = { 'title' : 'Dashboard' }
    return render(request, 'frontend/dashboard.html', context)
