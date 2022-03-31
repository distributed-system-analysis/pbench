import React,{useState} from 'react';
import { useNavigate } from 'react-router-dom';
import {useDispatch } from 'react-redux';
import pbenchIcon from '../../assets/white.d427c087.svg'
import githubIcon from '../../assets/github.svg'
import googleIcon from '../../assets/googleplus.png'
import redhatIcon from '../../assets/redhat.svg'
import emailIcon from '../../assets/email.png'
import passwordIcon from '../../assets/lock.svg'
import userIcon from '../../assets/user.png'
import axios from 'axios';
import validator from 'validator';
import "animate.css/animate.min.css";
import "react-toastify/dist/ReactToastify.css";
import { ToastContainer,cssTransition } from "react-toastify";
import './authComponent.css';
import { storeLoginInfo } from '../../redux/loginInfo/loginActions';
import wrongCredentials from '../../services/toast/wrongCredentials';
import accountCreated from '../../services/toast/accountCreated';
import incompleteData from '../../services/toast/incompleteData';
import userExist from '../../services/toast/userExist';
import wrongPasswordEmail from '../../services/toast/wrongPasswordEmail';
import passwordMismatch from '../../services/toast/passwordMismatch';
import checkPassword from '../../utils/checkPassword';

const bounce = cssTransition({
  enter: "animate__animated animate__bounceIn",
  exit: "animate__animated animate__bounceOut"
});
function AuthComponent() {
  const [username,setUsername]=useState('')
  const [password,setPassword]=useState('')
  const [firstName,setFirstName]=useState('')
  const [lastName,setLastName]=useState('')
  const [newUserName,setNewUserName]=useState('')
  const [email,setEmail]=useState('')
  const [signupPassword,setSignUpPassword]=useState('')
  const [reEnterPassword,setReEnterPassword]=useState('')
  const dispatch=useDispatch();
  const navigate=useNavigate();
  const resetConditions=()=>{
    document.getElementsByClassName('bullet-icon')[0].style.backgroundColor="#d4d4d4"
    document.getElementsByClassName('bullet-icon')[1].style.backgroundColor="#d4d4d4"
    document.getElementsByClassName('bullet-icon')[2].style.backgroundColor="#d4d4d4"
    document.getElementsByClassName('bullet-icon')[3].style.backgroundColor="#d4d4d4"
    document.querySelectorAll('.password-rule span')[0].style.color="#d4d4d4"
    document.querySelectorAll('.password-rule span')[1].style.color="#d4d4d4"
    document.querySelectorAll('.password-rule span')[2].style.color="#d4d4d4"
    document.querySelectorAll('.password-rule span')[3].style.color="#d4d4d4"
  }
  const handleUsername=(e)=>{
     setUsername(e.target.value)
  }
  const handlePassword=(e)=>{
      setPassword(e.target.value)
  }
  const handleLogIn=()=>{
    axios.post(`${process.env.REACT_APP_LOGIN}`,{
      username:username,
      password:password
    },{
      headers:{
        'Content-Type':'application/json',
        'Accept':'application/json'
      }
    }).then(res=>{
      localStorage.setItem('user',res.data.username)
    localStorage.setItem('token',res.data.auth_token)
      dispatch(storeLoginInfo({owner:res.data.username,
        token:res.data.auth_token,
        isLogin:true
    }))
    navigate(`/dashboard/${res.data.username}`);
    }).catch(err=>{
      wrongCredentials(bounce)
    })
  }
  const handleSignUpPassword=(e)=>{
    
    
    if(e.target.value.length>=8)
    {
        const bullet=document.getElementsByClassName('bullet-icon');
        bullet[0].style.backgroundColor='#6BA0F1'
        document.querySelectorAll('.password-rule span')[0].style.color='#0A0606'
        
    }
    else if(e.target.value.length<8)
    {
      const bullet=document.getElementsByClassName('bullet-icon');
      bullet[0].style.backgroundColor='#d4d4d4'
      document.querySelectorAll('.password-rule span')[0].style.color='#d4d4d4'
    }
    if(/[A-Z]/.test(e.target.value))
    {
      const bullet=document.getElementsByClassName('bullet-icon');
        bullet[1].style.backgroundColor='#6BA0F1'
        document.querySelectorAll('.password-rule span')[1].style.color='#0A0606'
    }
    else
    {
      const bullet=document.getElementsByClassName('bullet-icon');
      bullet[1].style.backgroundColor='#d4d4d4'
      document.querySelectorAll('.password-rule span')[1].style.color='#d4d4d4'
    }
    if(/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]+/.test(e.target.value))
     {
      const bullet=document.getElementsByClassName('bullet-icon');
      bullet[2].style.backgroundColor='#6BA0F1'
      document.querySelectorAll('.password-rule span')[2].style.color='#0A0606'
     }
     else
     {
      const bullet=document.getElementsByClassName('bullet-icon');
      bullet[2].style.backgroundColor='#d4d4d4'
      document.querySelectorAll('.password-rule span')[2].style.color='#d4d4d4'
     }
    if(/\d/.test(e.target.value))
    {
      const bullet=document.getElementsByClassName('bullet-icon');
      bullet[3].style.backgroundColor='#6BA0F1'
      document.querySelectorAll('.password-rule span')[3].style.color='#0A0606'
    }
     else
     {
      const bullet=document.getElementsByClassName('bullet-icon');
      bullet[3].style.backgroundColor='#d4d4d4'
      document.querySelectorAll('.password-rule span')[3].style.color='#d4d4d4'
     }
     
     setSignUpPassword(e.target.value)
  }
  const handleSignUp=()=>{
    if(signupPassword===reEnterPassword&&validator.isEmail(email)&&checkPassword(signupPassword))
    {
    axios.post(`${process.env.REACT_APP_REGISTER}`,{
        first_name:firstName,
        last_name:lastName,
        username:newUserName,
        email:email,
        password:signupPassword
    },{
      headers:{
      'Content-Type':'application/json',
      'Accept':'application/json'
    }
    }).then(res=>{
      resetConditions();
      setFirstName('')
      setLastName('')
      setNewUserName('')
      setEmail('')
      setSignUpPassword('')
      setReEnterPassword('')
      changeToSignIn();
      accountCreated(bounce)
    }).catch(err=>{
      if(firstName.length===0||lastName.length===0||newUserName.length===0)
      incompleteData(bounce)
      else
      userExist(bounce)
    })
    }
    else
    {  if(signupPassword===reEnterPassword)
      wrongPasswordEmail(bounce)
      else
      passwordMismatch(bounce)
    }
  }
  const changeToSignUp=()=>{
    const signIn=document.getElementsByClassName('login-box')
    const signUp=document.getElementsByClassName('signup-box')
    if(signIn[0].classList.contains('swapToSignIn'))
    signIn[0].classList.remove('swapToSignIn')
    if(signUp[0].classList.contains('replaceSignUp'))
    signUp[0].classList.remove('replaceSignUp')
    
    signIn[0].classList.add('swapToSignUp');
    signUp[0].classList.add('replaceSignIn');
  }
  const changeToSignIn=()=>{
    const signIn=document.getElementsByClassName('login-box')
    const signUp=document.getElementsByClassName('signup-box')
    signIn[0].classList.add('swapToSignIn');
    signUp[0].classList.add('replaceSignUp');
    signIn[0].classList.remove('swapToSignUp')
    signUp[0].classList.remove('replaceSignIn')
  }
  return (
    <div className='login-layout-container'>
    <div className='login-layout'>
      <div className='login-box'>
        <div className='pbench-login'>
          <h1>Sign In to Pbench</h1>
          <div className='pbench-login-icons'>
          <img src={githubIcon} alt="login with github" className='github-icon'></img>
          <img src={googleIcon} alt="login with google" className='google-icon'></img>
          <img src={redhatIcon} alt="login with redhat sso" className='redhat-icon'></img>
          </div>
          <div className='pbench-text'>
            <span>or use your pbench credentials</span>
          </div>
          <div className='pbench-enter-credentials'>
            <div className='pbench-enter-email'>
              <img src={emailIcon} alt='email' className='email-icon'></img>
              <input type='text' placeholder='Email' value={username} onChange={handleUsername} id="signInUsername"></input>
            </div>
            <div className='pbench-enter-password'>
              <img src={passwordIcon} alt='password' className='password-icon'></img>
              <input type='password' placeholder='Password' value={password} onChange={handlePassword} id="signInPassword"></input>
            </div>
            <div className='forget-password'>
              <div>
                Forgot your password?
              </div>
            </div>
            <div className='sign-in-button'>
              <button onClick={handleLogIn}>SIGN IN</button>
            </div>
            <div className='sign-up-link'>
              <p>Don't have an account?<span onClick={changeToSignUp}>Sign up</span> or <span onClick={()=>navigate('/dashboard/public')}>Browse Dashboard in Guest mode</span></p>
            </div>
          </div>
        </div>
        <div className='pbench-info'>
          <div className='pbench-info-container'>
          <img src={pbenchIcon} alt="pbench_logo" className='pbench-icon'></img>
        <div className='pbench-info-text'>
        <p>Pbench is a harness that allows data collection from a variety of tools while running a benchmark. 
          Pbench has some built-in script that run some common benchmarks.</p>
        </div>
        </div>
        </div>
      </div>
      <div className='signup-layout'>
      <div className='signup-box' id="signUpContainer">
         <div className='pbench-info-2'>
           <div className='pbench-info-2-container'>
           <img src={pbenchIcon} alt="pbench_logo" className='pbench-icon-2'></img>
           <div className='pbench-info-text-2'>
        <p>Pbench is a harness that allows data collection from a variety of tools while running a benchmark. 
          Pbench has some built-in script that run some common benchmarks.</p>
        </div>
           </div>
         </div>
         <div className='pbench-signup'>
            <h1>Create An Account</h1>
            <div className='pbench-enter-details'>
            <div className='pbench-enter-firstname'>
              <img src={userIcon} alt='firstname' className='user-icon'></img>
              <input type='text' placeholder='First Name' value={firstName} onChange={(e)=>setFirstName(e.target.value)}></input>
            </div>
            <div className='pbench-enter-lastname'>
              <img src={userIcon} alt='lastname' className='user-icon'></img>
              <input type='text' placeholder='Last Name' value={lastName} onChange={(e)=>setLastName(e.target.value)}></input>
            </div>
            <div className='pbench-enter-username'>
              <img src={userIcon} alt='username' className='user-icon'></img>
              <input type='text' placeholder='User Name' value={newUserName} onChange={(e)=>setNewUserName(e.target.value)}></input>
            </div>
            <div className='pbench-enter-email'>
              <img src={emailIcon} alt='email' className='email-icon'></img>
              <input type='text' placeholder='Email' value={email} onChange={(e)=>setEmail(e.target.value)}></input>
            </div>
            <div className='pbench-enter-password'>
              <img src={passwordIcon} alt='password' className='password-icon'></img>
              <input type='password' placeholder='Password' value={signupPassword} onChange={handleSignUpPassword}></input>
            </div>
            <div className='pbench-enter-password'>
              <img src={passwordIcon} alt='password' className='password-icon'></img>
              <input type='password' placeholder='Re-enter your password' value={reEnterPassword} onChange={(e)=>setReEnterPassword(e.target.value)}></input>
            </div>
            </div>
            <div className='password-rules'>
              <span className='password-title'>Password must contain at least</span>
              <div className='password-rule'>
                <div className='bullet-icon'></div>
                <span>8 characters</span>
              </div>
              <div className='password-rule'>
              <div className='bullet-icon'></div>
                <span>One uppercase letter</span>
              </div>
              <div className='password-rule'>
              <div className='bullet-icon'></div>
                <span>One special character</span>
              </div>
              <div className='password-rule'>
              <div className='bullet-icon'></div>
                <span>One Number</span>
              </div>
            </div>
            <div className='sign-in-button'>
              <button onClick={handleSignUp}>SIGN UP</button>
            </div>
            <div className='sign-in-link'>
              <p>Already have an account?<span onClick={changeToSignIn}>Log In</span></p>
            </div>
         </div>
      </div>
      </div>
    </div>
      
      <ToastContainer transition={bounce} position='top-center' hideProgressBar={true} autoClose={3000}/>
    </div>
  );
}

export default AuthComponent;
