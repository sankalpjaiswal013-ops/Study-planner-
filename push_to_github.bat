@echo off
cd /d "c:\Users\Lenovo\Downloads\studyplanner"

echo Setting up your Git profile for green contributions...
git config --global user.email "sankalpjaiswal013@gmail.com"
git config --global user.name "Sankalp Jaiswal"

echo Committing code...
git add .
git commit -m "Update application"

REM Remove the broken "origin" to start fresh
git remote remove origin 2>nul

:ask_url
echo.
echo =======================================================
echo ACTION REQUIRED:
echo Please provide the full URL of your GitHub repository.
echo Example: https://github.com/codeXpixel/studyplanner.git
echo =======================================================
echo.
set /p repo_url="Paste the GitHub URL here and press ENTER: "

if "%repo_url%"=="" (
    echo You didn't enter anything! Let's try again.
    goto :ask_url
)

git branch -M main
set repo_url=%repo_url:"=%
git remote add origin "%repo_url%"

echo.
echo Pushing to GitHub...
git push -u origin main

echo.
echo Finished! Check the messages above for any errors.
