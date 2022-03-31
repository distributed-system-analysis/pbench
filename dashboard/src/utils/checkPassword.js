function checkPassword(pswrd) {
    return pswrd.length>=8&&/[A-Z]/.test(pswrd)&&/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]+/.test(pswrd)&&/\d/.test(pswrd)
}

export default checkPassword