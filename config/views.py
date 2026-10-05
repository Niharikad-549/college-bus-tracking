from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


def page_not_found(request, exception=None):
	return render(request, 'errors/404.html', status=404)


def server_error(request):
	return render(request, 'errors/500.html', status=500)


@require_GET
def health_check(request):
	return JsonResponse({'status': 'ok'})