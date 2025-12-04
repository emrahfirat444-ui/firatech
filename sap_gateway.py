"""
SAP RFC REST API Gateway
Streamlit uygulaması ile SAP arasında REST API aracılığı ile iletişim kurar
"""

from flask import Flask, jsonify, request
from datetime import datetime
import json
import os
from dotenv import load_dotenv
load_dotenv()
import requests

app = Flask(__name__)

# SAP RFC Konfigürasyonu
SAP_CONFIG = {
    "host": os.getenv('SAP_HOST', 'saplogonprod.yatas.com.tr'),
    "client": os.getenv('SAP_CLIENT', '00'),
    "sysnr": os.getenv('SAP_SYSNR', '00'),
    "user": os.getenv('SAP_USER', 'efirat'),
    "password": os.getenv('SAP_PASSWORD', ''),
    "lang": os.getenv('SAP_LANG', 'TR'),
    "group": os.getenv('SAP_GROUP', 'YATAS')
}


def get_sap_connection():
    """SAP bağlantısı oluştur"""
    try:
        from pyrfc import Connection
        conn = Connection(
            ashost=SAP_CONFIG["host"],
            sysnr=SAP_CONFIG["sysnr"],
            client=SAP_CONFIG["client"],
            user=SAP_CONFIG["user"],
            passwd=SAP_CONFIG["password"],
            lang=SAP_CONFIG["lang"]
        )
        return conn
    except Exception as e:
        return None


@app.route('/api/health', methods=['GET'])
def health():
    """API sağlık kontrolü"""
    return jsonify({"status": "ok", "message": "SAP REST API Gateway çalışıyor"})


@app.route('/api/pernr-from-email', methods=['POST'])
def get_pernr_from_email():
    """
    Email adresinden PERNR (Personel Numarası) bul
    POST: {"email": "user@yatas.com"}
    """
    try:
        data = request.json
        email = data.get('email', '')
        
        conn = get_sap_connection()
        if not conn:
            # Eğer pyrfc yok veya bağlantı kurulamadıysa demo modunda cevap dön
            if os.environ.get('SAP_GATEWAY_DEMO', '1') == '1':
                # Basit demo eşleme: email'e göre sabit PERNR döndür
                demo_map = {
                    'efirat@yatas.com': '00012345',
                    'demo@yatas.com': '00099999',
                    'admin@yatas.com': '00000001'
                }
                pernr = demo_map.get(email.lower(), '00000000')
                return jsonify({
                    "success": True,
                    "pernr": pernr,
                    "email": email,
                    "message": f"Demo PERNR bulundu: {pernr}"
                })

            return jsonify({
                "success": False,
                "message": "SAP bağlantısı kurulamadı"
            }), 500
        
        # HR_READ_INFOTYPE ile PA0105 (Communication) verilerini oku
        result = conn.call(
            'HR_READ_INFOTYPE',
            INFTY='0105',
            ITFLG='*'
        )
        
        conn.close()
        
        # Sonuçlardan email eşleşmesini ara
        if 'PERSON' in result:
            for person in result['PERSON']:
                person_email = person.get('USRID_LONG', '')
                if email.lower() in person_email.lower():
                    pernr = person.get('PERNR')
                    if pernr:
                        return jsonify({
                            "success": True,
                            "pernr": pernr,
                            "email": email,
                            "message": f"PERNR bulundu: {pernr}"
                        })
        
        return jsonify({
            "success": False,
            "message": f"Email '{email}' SAP'te bulunamadı"
        }), 404
    
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"RFC Hatası: {str(e)}",
            "error_type": type(e).__name__
        }), 500


@app.route('/api/leave-balance', methods=['POST'])
def get_leave_balance():
    """
    Personel numarasından izin bakiyesi al
    POST: {"pernr": "00001234", "year": 2025}
    """
    try:
        data = request.json
        pernr = data.get('pernr', '')
        year = data.get('year', datetime.now().year)
        
        conn = get_sap_connection()
        if not conn:
            # Demo fallback when SAP not available
            if os.environ.get('SAP_GATEWAY_DEMO', '1') == '1':
                # Simple demo data
                demo_balance = {
                    'ENTITLED': 20,
                    'USED': 5,
                    'AVAILABLE': 15,
                    'PENDING': 1
                }
                return jsonify({
                    "success": True,
                    "personnel_id": pernr,
                    "year": year,
                    "total_leave_days": int(demo_balance.get('ENTITLED', 0)),
                    "used_leave_days": int(demo_balance.get('USED', 0)),
                    "remaining_leave_days": int(demo_balance.get('AVAILABLE', 0)),
                    "pending_leave_requests": int(demo_balance.get('PENDING', 0)),
                    "rfc_function": "PT_GET_LEAVE_BALANCE (demo)",
                    "raw_result": demo_balance
                })

            return jsonify({
                "success": False,
                "message": "SAP bağlantısı kurulamadı"
            }), 500

        # PT_GET_LEAVE_BALANCE RFC çağrısı
        result = conn.call(
            'PT_GET_LEAVE_BALANCE',
            IV_PERNR=pernr,
            IV_YEAR=str(year),
            IV_ABSENCE_TYPE=''
        )

        conn.close()

        # ET_BALANCE tablosundan veri çıkar
        balance_list = result.get('ET_BALANCE', [])
        balance_data = balance_list[0] if balance_list else {}

        return jsonify({
            "success": True,
            "personnel_id": pernr,
            "year": year,
            "total_leave_days": int(balance_data.get('ENTITLED', 0)),
            "used_leave_days": int(balance_data.get('USED', 0)),
            "remaining_leave_days": int(balance_data.get('AVAILABLE', 0)),
            "pending_leave_requests": int(balance_data.get('PENDING', 0)),
            "rfc_function": "PT_GET_LEAVE_BALANCE",
            "raw_result": balance_data
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"RFC Hatası: {str(e)}",
            "error_type": type(e).__name__,
            "pernr": pernr
        }), 500


@app.route('/api/employee-data', methods=['POST'])
def get_employee_data():
    """
    Personel verilerini al (BAPI_EMPLOYEE_GETDATA)
    POST: {"pernr": "00001234"}
    """
    try:
        data = request.json
        pernr = data.get('pernr', '')
        
        conn = get_sap_connection()
        if not conn:
            # Demo fallback
            if os.environ.get('SAP_GATEWAY_DEMO', '1') == '1':
                demo_person = {
                    'PERSONAL_DATA': {
                        'FIRSTNAME': 'Demo',
                        'LASTNAME': 'Kullanıcı',
                        'GENDER': 'M'
                    },
                    'ORGANIZATION_DATA': {
                        'DEPARTMENT': 'IT',
                        'POSITION': 'Test'
                    }
                }
                return jsonify({
                    "success": True,
                    "personnel_id": pernr,
                    "employee_data": demo_person['PERSONAL_DATA'],
                    "organization_data": demo_person['ORGANIZATION_DATA'],
                    "raw_result": demo_person
                })

            return jsonify({
                "success": False,
                "message": "SAP bağlantısı kurulamadı"
            }), 500

        # BAPI_EMPLOYEE_GETDATA RFC çağrısı
        result = conn.call(
            'BAPI_EMPLOYEE_GETDATA',
            EMPLOYEE_NUMBER=pernr
        )

        conn.close()

        return jsonify({
            "success": True,
            "personnel_id": pernr,
            "employee_data": result.get('PERSONAL_DATA', {}),
            "organization_data": result.get('ORGANIZATION_DATA', {}),
            "raw_result": result
        })
    
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"RFC Hatası: {str(e)}",
            "error_type": type(e).__name__,
            "pernr": pernr
        }), 500


if __name__ == '__main__':
    print("SAP REST API Gateway başlatılıyor...")
    print("Endpoints:")
    print("  GET  /api/health - Sağlık kontrolü")
    print("  POST /api/pernr-from-email - Email'den PERNR bul")
    print("  POST /api/leave-balance - İzin bakiyesi")
    print("  POST /api/employee-data - Personel verisi")
    print("\nÖrnek:")
    print('  curl -X POST http://localhost:5000/api/leave-balance -H "Content-Type: application/json" -d \'{"pernr":"00001234","year":2025}\'')
    
    # Run without reloader/debugger to avoid threading/select issues in background
    app.run(debug=False, use_reloader=False, host='0.0.0.0', port=5000)

# Test isteği (örnek) - manuel olarak çalıştırın, otomatik çalıştırma devre dışı bırakıldı
# Örnek komut:
# curl -X POST http://127.0.0.1:5000/api/leave-balance -H "Content-Type: application/json" -d '{"pernr":"00012345","year":2025}'
