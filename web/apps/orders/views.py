# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response

class OrdersPingView(APIView):
    """
    Endpoint de salud del módulo orders.
    Mantiene DRF para homogeneidad y futura expansión.
    """
    def get(self, request):
        return Response({"ok": True})
