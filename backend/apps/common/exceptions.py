from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """Custom exception handler standardizing error formats across the API."""
    response = exception_handler(exc, context)

    if response is not None:
        custom_data = {
            "success": False,
            "status_code": response.status_code,
            "error": response.data if isinstance(response.data, (dict, list, str)) else str(exc),
        }
        response.data = custom_data

    return response
