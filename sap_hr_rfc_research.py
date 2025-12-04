"""
SAP HR Modülü - RFC Fonksiyonları Araştırması
Research on SAP HR Module RFC Functions

Bu dosya, SAP sisteminde HR (Human Resources) modülünde yaygın olarak kullanılan
RFC (Remote Function Call) fonksiyonlarını ve bunların parametrelerini içerir.
"""

# ============================================================================
# 1. EMAIL ADRESİNDEN PERSONEL NUMARASI (PERNR) BULMA
# ============================================================================

"""
AŞAMA 1: Email adresinden PERNR bulma işlemi
Genellikle iki yoldan yapılır:

A) Direct RFC Fonksiyonlar:
   - RFC fonksiyonları doğrudan email ile arama yapmaz
   - Genellikle custom RFC yazılması gerekir VEYA
   - Indirect yoldan table lookup yapılır

B) Standart Tablolar Üzerinden:
   - USR01 / USR02 (SAP User tablosu)
   - PA0001 (Personal Data tablosu)
   - PA0105 (Communication tablosu - Email için)
"""

SAP_RFC_EMAIL_TO_PERNR = {
    "description": "Email adresinden PERNR bulma",
    "method": "Custom RFC + Standard Tables",
    "workflow": [
        "1. PA0105 tablosuna query at (Telefon/Email bilgileri için)",
        "2. PA0105.USRID veya PA0105.TEL1 ile email'i ara",
        "3. Eşleşen kaydın PA0105.PERNR'ini döndür",
        "4. Alternatif: USR01/USR02 tablosundan user bulup PA0001'den PERNR çek"
    ],
    "tables_used": ["PA0105", "PA0001", "USR01", "USR02"],
    "possible_custom_rfc": "Z_GET_PERNR_FROM_EMAIL"
}

"""
STANDART SAP RFC'LER - EMAIL TO PERNR:

1. RFC: "BAPI_USER_GET_DETAIL" (User Management)
   - Amacı: User details almak
   - Input: USERNAME
   - Output: User bilgileri, mail address vs.
   - Modül: User Management
   - ANCAK: Bu RFC user -> employee linkini otomatik yapmaz

2. RFC: "BAPI_EMPLOYEE_GETDATA" (Employee Data)
   - Amacı: Personel bilgilerini getirmek
   - Input: PERNR (personel numarası)
   - Output: Employee details
   - Modül: HR - Personnel Administration
   - NOT: PERNR bilinmelidir, email'den PERNR bulmaz

3. RFC: "HR_READ_INFOTYPE" (Infotype Reader)
   - Amacı: İnsan kaynakları infotype verilerini okumak
   - Input: PERNR, INFOTYPE, DATE RANGE
   - Output: Infotype records
   - Modül: HR-PA
   - Infotype 105 = Communication (Email/Telefon)
"""

BAPI_USER_GET_DETAIL = {
    "name": "BAPI_USER_GET_DETAIL",
    "description": "SAP User detaylarını getirmek",
    "type": "BAPI",
    "module": "User Management",
    "input_parameters": {
        "USERNAME": "str - SAP Kullanıcı adı (required)",
        "CACHE_RESULTS": "str - Cache etmek için"
    },
    "output_parameters": {
        "USERDETAIL": "structure - Kullanıcı detayları",
        "DEFAULTS": "structure - Default değerler",
        "ACTIVITYGROUPS": "table - Activity grupları",
        "ADDRESS": "structure - Adres info"
    },
    "output_fields": {
        "USERDETAIL-EMAIL": "E-mail adresi",
        "USERDETAIL-GNAME": "Kullanıcı adı",
        "USERDETAIL-NAME": "Soyadı"
    },
    "note": "User-Employee linkini yapmak için ek query gerekir"
}

HR_READ_INFOTYPE = {
    "name": "HR_READ_INFOTYPE",
    "description": "İnsan kaynakları infotype verilerini okumak",
    "type": "RFC Function",
    "module": "HR-PA (Personnel Administration)",
    "input_parameters": {
        "PERNR": "int - Personel numarası (required)",
        "INFTY": "str - Infotype numarası, ör: '0001', '0105' (required)",
        "BEGDA": "date - Başlangıç tarihi",
        "ENDDA": "date - Bitiş tarihi",
        "SYNCHRON": "str - Senkron modu (X = synchron)",
    },
    "output_parameters": {
        "INFTY": "Infotype numarası",
        "SUBTY": "Subtype",
        "OBJECTID": "Object ID",
        "LOCK": "Lock durumu",
        "RETURN": "Return codes",
        "RECORDS": "table - Infotype kayıtları"
    },
    "infotypes": {
        "0001": "Organizational Data",
        "0002": "Personal Data",
        "0105": "Communication (E-mail, Phone, etc.)",
        "0021": "Family Members",
        "2001": "Leave Entitlements",
        "2005": "Leave Master",
        "2006": "Leave/Absence Status"
    },
    "example": "PERNR=12345, INFTY='0105' -> E-mail, Telefon bilgisi döner"
}

# ============================================================================
# 2. PERSONEL NUMARASI İLE İZİN/LEAVE GÜNLERİNİ BULMA
# ============================================================================

"""
STANDART SAP RFC'LER - LEAVE DATA:

1. RFC: "HR_READ_INFOTYPE" (Infotype Reader)
   - Kullanım: INFTY = '2001' (Leave Entitlements) veya '2005' (Leave Master)
   - Input: PERNR, INFTYPE
   - Output: Leave detayları

2. RFC: "BAPI_EMPLOYEE_GETDATA" (Employee Data)
   - Amacı: Employee'nin tüm verilerini getirmek
   - Input: PERNR
   - Output: Temel employee bilgileri

3. RFC: "PT_GET_LEAVE_BALANCE" (Payroll/Time Management - Özel)
   - Amacı: Leave balance/used days almak
   - Input: PERNR, LEAVE_TYPE, DATE
   - Output: Leave balance detayları
   - Modül: PT (Payroll), TM (Time Management)

4. RFC: "HR_GET_INFOTYPES_COMPLETE" (Complete Infotype Data)
   - Amacı: Tüm infotype verilerini almak
   - Input: PERNR, DATE RANGE
   - Output: Tüm HR veriler

5. RFC: "BAPI_COMPANYCODE_GETDETAIL" (Company Code Info)
   - Kullanım: Leave policies vs. company specific bilgi
"""

HR_READ_INFOTYPE_LEAVE = {
    "name": "HR_READ_INFOTYPE",
    "usage_for_leave": "Leave/Absence bilgisi için",
    "infotypes_for_leave": {
        "2001": {
            "name": "Leave Entitlements",
            "description": "Yıllık izin hakkı, kullanılabilir günler",
            "fields": ["PERNR", "BEGDA", "ENDDA", "LEAVET", "ENTDY", "DIVID", "STATUS"]
        },
        "2005": {
            "name": "Leave Master Data",
            "description": "Leave türü master verileri",
            "fields": ["PERNR", "LEAVET", "VALUT", "QUOTA", "TAKDA"]
        },
        "2006": {
            "name": "Leave/Absence Status",
            "description": "Leave başvurusu, onay durumu",
            "fields": ["PERNR", "BEGDA", "ENDDA", "LEAVET", "APPRV", "STAT", "RCOND"]
        }
    },
    "module": "HR-PA, TM (Time Management)",
    "input_parameters": {
        "PERNR": "int - Personel numarası",
        "INFTY": "str - Infotype (2001, 2005, 2006)",
        "BEGDA": "date - Başlangıç tarihi (örn: 20250101)",
        "ENDDA": "date - Bitiş tarihi (örn: 20251231)",
    }
}

PT_GET_LEAVE_BALANCE = {
    "name": "PT_GET_LEAVE_BALANCE",
    "description": "Personel izin bakiyesi hesaplama",
    "type": "RFC Function",
    "module": "PT (Payroll/Time Management)",
    "input_parameters": {
        "PERNR": "int - Personel numarası (required)",
        "LEAVETYPE": "str - İzin türü (ör: A001, A002)",
        "DATE_FROM": "date - Tarih aralığı başlangıcı",
        "DATE_TO": "date - Tarih aralığı bitişi",
        "COMPANY_CODE": "str - Şirket kodu"
    },
    "output_parameters": {
        "ENTITLED_DAYS": "decimal - Toplam hak",
        "USED_DAYS": "decimal - Kullanılan günler",
        "AVAILABLE_DAYS": "decimal - Kullanılabilir günler",
        "PENDING_DAYS": "decimal - Beklemede olan günler",
        "CARRYOVER_DAYS": "decimal - Devreden günler",
        "RETURN_CODE": "int - Başarı/hata kodu"
    },
    "note": "PT_GET_LEAVE_BALANCE fonksiyonu SAP sisteminin PT modülünde olup, leave bakiyesi hesaplamak için kullanılır"
}

BAPI_EMPLOYEE_GETDATA = {
    "name": "BAPI_EMPLOYEE_GETDATA",
    "description": "Employee detaylarını getirmek",
    "type": "BAPI",
    "module": "HR - Personnel Administration",
    "input_parameters": {
        "EMPLOYEE_ID": "str - Personel numarası (required)",
        "INFOTYPE_SELECTION": "table - Seçili infotype'lar",
        "DATE": "date - Sorgu tarihi"
    },
    "output_parameters": {
        "PERSONAL_DATA": "structure",
        "ORGANIZATIONAL_DATA": "structure",
        "COMPANY_DATA": "structure",
        "COMMUNICATION": "table",
        "EMPLOYEE": "str",
        "EMPLOYEE_NAME": "str",
        "RETURN": "table - Return messages"
    },
    "note": "Detaylı employee bilgileri için INFOTYPE_SELECTION kullanıp specific infotype'ları belirtebilirsiniz"
}

# ============================================================================
# 3. EN YAYGON KULLANILAN HR RFC FONKSİYONLARI ÖZETİ
# ============================================================================

COMMON_SAP_HR_RFC_SUMMARY = {
    "tier_1_most_common": {
        "1": {
            "name": "BAPI_EMPLOYEE_GETDATA",
            "purpose": "Employee verilerini almak",
            "input": "PERNR (Personel No)",
            "output": "Employee details, leave info, organizational data",
            "module": "HR-PA",
            "frequency": "VERY HIGH"
        },
        "2": {
            "name": "HR_READ_INFOTYPE",
            "purpose": "Spesifik infotype verilerini okumak",
            "input": "PERNR, INFTY, DATE RANGE",
            "output": "Infotype kayıtları",
            "module": "HR-PA",
            "frequency": "VERY HIGH",
            "note": "Infotype 2001/2005/2006 = Leave data"
        },
        "3": {
            "name": "PT_GET_LEAVE_BALANCE",
            "purpose": "Leave bakiyesi hesaplamak",
            "input": "PERNR, LEAVE_TYPE, DATE",
            "output": "Entitled, used, available days",
            "module": "PT (Payroll/Time)",
            "frequency": "HIGH",
            "note": "Leave balance calculations için optimal"
        }
    },
    
    "tier_2_common": {
        "1": {
            "name": "HR_GET_CURRENT_EMPLOYEE",
            "purpose": "Mevcut employee'leri getirmek",
            "input": "Selection criteria",
            "output": "Employee list",
            "module": "HR-PA"
        },
        "2": {
            "name": "BAPI_ABSENCE_GETLIST",
            "purpose": "Absence/Leave başvuruları almak",
            "input": "PERNR, DATE RANGE",
            "output": "Absence records",
            "module": "HR-PA"
        },
        "3": {
            "name": "HR_EMPLOYEE_SCREEN_INFOTYPE_READ",
            "purpose": "Screen tabanlı infotype verisi okuması",
            "input": "PERNR, INFTY, SCREEN",
            "output": "Infotype data with screen layout",
            "module": "HR-PA"
        }
    },

    "tier_3_specialized": {
        "1": {
            "name": "PT_SIMULATION_GET_RESULT",
            "purpose": "Payroll simulation sonuçları",
            "module": "PT"
        },
        "2": {
            "name": "HR_MAINTAIN_INFOTYPE",
            "purpose": "Infotype verilerini değiştirmek (Create/Update/Delete)",
            "module": "HR-PA",
            "note": "Writing işlemi için, VALIDATE_INFOTYPE kullanılabilir"
        },
        "3": {
            "name": "BAPI_ATTENDANCE_GET_LIST",
            "purpose": "Attendance/Devamsızlık bilgisi",
            "module": "HR-TM"
        }
    }
}

# ============================================================================
# 4. EMAIL -> PERNR -> LEAVE WORKFLOW ÖRNEK KOD
# ============================================================================

"""
Python Pseudo-Code Example:

from pyrfc import Connection

# SAP Connection
conn = Connection(
    ashost='10.20.30.40',
    sysnr='00',
    client='100',
    user='username',
    passwd='password',
    lang='EN'
)

# STEP 1: Email'den PERNR bulma (HR_READ_INFOTYPE kullanarak)
# PA0105 (Communication) infotype'ı email bilgisini içerir

try:
    # Önce tüm personelleri listele ve email ara
    # Veya custom RFC Z_GET_PERNR_FROM_EMAIL kullan
    
    result = conn.call(
        'HR_READ_INFOTYPE',
        PERNR=12345,           # Bilinen PERNR
        INFTY='0105',          # Communication infotype
        BEGDA='20250101',
        ENDDA='20251231'
    )
    
    # result['RECORDS'] = [
    #     {'TEL1': '+90-212-xxx-xxxx', 'EMAIL': 'john@company.com', ...},
    #     ...
    # ]
    
except Exception as e:
    print(f"Error: {e}")

# STEP 2: PERNR'den Leave bilgisini alma

try:
    leave_data = conn.call(
        'HR_READ_INFOTYPE',
        PERNR=12345,
        INFTY='2006',          # Leave/Absence Status
        BEGDA='20250101',
        ENDDA='20251231'
    )
    
    # leave_data['RECORDS'] = [
    #     {'BEGDA': '20250115', 'ENDDA': '20250120', 'LEAVET': 'A001', 
    #      'APPRV': '1', 'STAT': 'APPROVED', ...},
    #     ...
    # ]
    
except Exception as e:
    print(f"Error: {e}")

# STEP 3: Leave Balance almak (PT_GET_LEAVE_BALANCE)

try:
    balance = conn.call(
        'PT_GET_LEAVE_BALANCE',
        PERNR=12345,
        LEAVETYPE='A001',      # Annual Leave
        DATE_FROM='20250101',
        DATE_TO='20251231'
    )
    
    # balance = {
    #     'ENTITLED_DAYS': 20.0,
    #     'USED_DAYS': 5.0,
    #     'AVAILABLE_DAYS': 15.0,
    #     'PENDING_DAYS': 2.0
    # }
    
except Exception as e:
    print(f"Error: {e}")

conn.close()
"""

# ============================================================================
# 5. SAP INFOTYPE KODLARI (Leave İçin Önemli Olanlar)
# ============================================================================

SAP_INFOTYPES_REFERENCE = {
    "0001": "Organizational Data",
    "0002": "Personal Data",
    "0008": "Basic Pay",
    "0015": "Additional Personal Data",
    "0021": "Family Members",
    "0022": "Insurance",
    "0023": "Fiscal Data",
    "0024": "External",
    "0025": "Recurring Deductions",
    "0026": "Other/Previous Employment",
    "0027": "Membership Fees",
    "0028": "Tax",
    "0029": "Garnishee",
    "0030": "Internal",
    "0040": "Bank Details",
    "0041": "Notification of Payroll",
    "0050": "Accident Insurance",
    "0051": "Unemployment Insurance",
    "0080": "Tax Data",
    "0081": "Supplementary CRA",
    "0082": "Supplementary CRA (Cont.)",
    "0083": "Supplementary CRA (Cont.)",
    "0084": "Supplementary CRA (Cont.)",
    "0085": "Supplementary CRA (Cont.)",
    "0090": "Work Contract",
    "0100": "Payroll Status",
    "0101": "Organizational Assignment",
    "0102": "Job",
    "0103": "Salary",
    "0104": "Previous Employment",
    "0105": "Communication (EMAIL, PHONE, FAX, etc.) *** IMPORTANT ***",
    "0106": "Address (Residential Address)",
    "0107": "Professional Qualification",
    "0108": "External Work Activity",
    "0109": "Reference Person",
    "0110": "Education",
    "0111": "Previous Employer",
    "0112": "Previous Position",
    "0113": "Work Experience",
    "0114": "Military Service",
    "0115": "Organization Assignment (Cont.)",
    "0116": "Permit",
    "0117": "Training Course",
    "0118": "Language",
    "0119": "Travel",
    "0120": "Visa",
    "0121": "Repeat Entry",
    
    # *** LEAVE/ABSENCE INFOTYPES ***
    "2001": "Leave Entitlements (Yıllık izin hakkı) *** IMPORTANT ***",
    "2002": "Leave Accrual (İzin tahakkuku)",
    "2003": "Leave Accrual Validity (Tahakkuk geçerliliği)",
    "2005": "Leave Master Data (İzin master verileri) *** IMPORTANT ***",
    "2006": "Leave/Absence Status (İzin başvurusu durumu) *** IMPORTANT ***",
    "2007": "Overtime Correction (Fazla çalışma düzeltmesi)",
    "2008": "Leave Revaluation (İzin yeniden değerlendirmesi)",
    "2009": "Leave Compensation (İzin tazminatı)",
}

# ============================================================================
# 6. EMAIL -> PERNR MAPPING YAPMAK İÇİN KULLANILABİLECEK ALTERNATIVE YOLLAR
# ============================================================================

EMAIL_TO_PERNR_METHODS = {
    "Method_1_PA0105_Direct": {
        "description": "PA0105 tablosundan doğrudan email ile arama",
        "table": "PA0105",
        "query_field": "PA0105.TEL1 or PA0105.TELX",
        "return_field": "PA0105.PERNR",
        "advantages": ["Hızlı", "Doğrudan access"],
        "disadvantages": ["Table access gerekli", "RFC değil, direct table access"]
    },
    
    "Method_2_ADR6_Address_Table": {
        "description": "ADR6 (Address tablosu) email alanından",
        "table": "ADR6",
        "relationship": "ADR6 -> HRP1000 (Address linking) -> PA0001",
        "fields": ["ADR6.PERSNUMBER (email)", "ADR6.OBJ_ID", "HRP1000.OTYPE", "HRP1000.OBJID"],
        "note": "Daha karmaşık ama email için kullanılabilir"
    },
    
    "Method_3_Custom_RFC": {
        "description": "Custom Z_* RFC fonksiyonu yazılması",
        "module": "Custom module",
        "logic": [
            "HR_READ_INFOTYPE çağırma INFTY=0105 ile",
            "OR doğru PA0105 tablosundan SELECT yapma",
            "Email parametresi ile eşleştir",
            "PERNR döndür"
        ],
        "name_example": "Z_GET_PERNR_FROM_EMAIL",
        "pros": ["Custom ihtiyaçlara uygun", "Optimize edilmiş"],
        "cons": ["Custom development gerekli", "Maintenance zorunlu"]
    },
    
    "Method_4_User_Management": {
        "description": "SAP User -> Employee mapping",
        "steps": [
            "1. BAPI_USER_GET_DETAIL ile username'den user detail al",
            "2. USER_NAME'den email al",
            "3. USR02 tablosundan EMPLAREA/PERSAREA bilgisi çek",
            "4. PA0001 ile PERNR bağlantısını yap"
        ],
        "note": "User-Employee linkinin kurulu olması gerekir"
    }
}

# ============================================================================
# 7. SAP MODULES VE RFC DISCOVERY TOOLS
# ============================================================================

SAP_DISCOVERY_INFO = {
    "how_to_find_rfcs": {
        "1": "SAP GUI -> SE37 (Function Builder) -> Rfc'leri ara",
        "2": "SAP GUI -> SICF -> WS04SBDC service'i kontrolü",
        "3": "SAP GUI -> Transaction RFCLIST -> Tüm RFC'ler listesi",
        "4": "SAP GUI -> Transaction SM59 -> RFC Destinations",
        "5": "SAP Portal -> Documentation -> HR Module RFC List"
    },
    
    "how_to_read_tables": {
        "1": "SAP GUI -> SE11 (ABAP Dictionary) -> Table name gir",
        "2": "SAP GUI -> SE16 (Table Browser) -> Veri görüntüleme",
        "3": "SAP GUI -> SE16N (Enhanced Table Browser) -> Advanced search"
    },
    
    "modules": {
        "HR": "Human Resources",
        "PA": "Personnel Administration (HR-PA)",
        "TM": "Time Management (HR-TM)",
        "PT": "Payroll (HR-PT)",
        "OM": "Organization Management (HR-OM)",
        "LMS": "Learning Management System",
        "EP": "Employee Portal",
        "EM": "Employee Management"
    },
    
    "important_transactions": {
        "PA20": "Personnel records display",
        "PA30": "Personnel records modify",
        "INFOTYPES": "Infotype maintenance",
        "PA_SAL": "Salary information",
        "PA_LEAVE": "Leave infotype",
        "PZ70": "Employee Self-Service Leave Request",
        "CATSDB": "Time Tracking"
    }
}

# ============================================================================
# 8. ÖZET - SORULAR İÇİN CEVAPLAR
# ============================================================================

SUMMARY = {
    "soru_1_email_den_pernr": {
        "sorun": "Email adresinden personel numarası (PERNR) bulma",
        "cevap": [
            "1. Standart RFC: HR_READ_INFOTYPE (INFTY='0105' - Communication)",
            "2. Tablo: PA0105 (Communication infotype raw data)",
            "3. Custom RFC: Z_GET_PERNR_FROM_EMAIL yazılması önerilir",
            "4. Alternatif: ADR6 (Address table) veya User Management integration"
        ],
        "en_iyi_yol": "Custom RFC yazarak OR direct PA0105 table access yaparak"
    },
    
    "soru_2_pernr_den_leave": {
        "sorun": "Personel numarası ile izin/leave günlerini bulma",
        "cevap": [
            "1. RFC: HR_READ_INFOTYPE (INFTY='2006' - Leave Status)",
            "2. RFC: PT_GET_LEAVE_BALANCE (Bakiye hesaplama)",
            "3. RFC: BAPI_EMPLOYEE_GETDATA (Tüm employee data)",
            "4. Infotype 2001: Leave Entitlements (hak)",
            "5. Infotype 2005: Leave Master Data (leave türleri)"
        ],
        "en_iyi_kombinasyon": "HR_READ_INFOTYPE (2006) + PT_GET_LEAVE_BALANCE"
    },
    
    "soru_3_most_common_rfc": {
        "top_1": {
            "name": "BAPI_EMPLOYEE_GETDATA",
            "module": "HR-PA",
            "use": "Employee detayları almak"
        },
        "top_2": {
            "name": "HR_READ_INFOTYPE",
            "module": "HR-PA",
            "use": "Spesifik infotype verisi almak"
        },
        "top_3": {
            "name": "PT_GET_LEAVE_BALANCE",
            "module": "PT",
            "use": "Leave bakiyesi hesaplama"
        }
    }
}

if __name__ == "__main__":
    print("=" * 80)
    print("SAP HR RFC RESEARCH DOCUMENT")
    print("=" * 80)
    print("\nBu dosya SAP HR modülü RFC fonksiyonlarının detaylı araştırmasını içerir.")
    print("Lütfen özel RFC implementasyonu için SAP sisteminizdeki SE37 transaction'ında")
    print("RFC fonksiyonlarını doğrudan kontrol edin.")
    print("\nDetaylı bilgi için bu dosyadaki struktureleri inceleyiniz.")
    print("=" * 80)
