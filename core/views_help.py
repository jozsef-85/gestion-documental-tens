from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def manual_usuario(request):
    return render(request, 'manual_usuario.html')
