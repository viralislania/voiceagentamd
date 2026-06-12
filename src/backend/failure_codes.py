FAILURE_CODES: dict[str, dict] = {
    "INSUFFICIENT_FUNDS": {
        "reason": "Account balance was lower than the transfer amount.",
        "next_steps": ["Add funds and retry", "Try a smaller amount"],
        "complaint_eligible": False,
    },
    "DAILY_LIMIT_EXCEEDED": {
        "reason": "Transfer exceeded the daily transaction limit.",
        "next_steps": ["Retry tomorrow", "Request a limit increase via the app"],
        "complaint_eligible": False,
    },
    "BENEFICIARY_BANK_DOWN": {
        "reason": "Beneficiary bank's systems were temporarily unavailable.",
        "next_steps": ["Retry after some time", "Raise a complaint if amount was debited"],
        "complaint_eligible": True,
    },
    "TIMEOUT": {
        "reason": "Transaction timed out at the network switch.",
        "next_steps": ["Check if amount was debited", "Raise a complaint if debited"],
        "complaint_eligible": True,
    },
    "INVALID_ACCOUNT": {
        "reason": "Beneficiary account number or IFSC is incorrect.",
        "next_steps": ["Verify account details with the payee"],
        "complaint_eligible": False,
    },
    "UPI_PIN_BLOCKED": {
        "reason": "UPI PIN was entered incorrectly too many times.",
        "next_steps": ["Reset your UPI PIN in app settings"],
        "complaint_eligible": False,
    },
}
