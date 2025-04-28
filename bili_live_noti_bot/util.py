def isValidPositiveInt(input: str) -> bool:
    """
        判斷是否為格式正確的正整數
    """
    return input.isnumeric() and input.isascii() and int(input) > 0 and str(int(input)) == input