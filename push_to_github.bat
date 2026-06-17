@echo off
cd /d "c:\Users\Lenovo\Downloads\studyplanner"

echo Setting up your Git profile for green contributions...
git config --global user.email "sankalpjaiswal013@gmail.com"
git config --global user.name "Sankalp Jaiswal"

if not exist .git (
    echo Initializing a new Git repository...
    git init
)

echo Committing code...
git add .
git commit -m "Update application"

git remote | findstr "origin" >nul
if errorlevel 1 (
    echo.
    echo =======================================================
    echo ACTION REQUIRED:
    echo Please provide the URL of your empty GitHub repository.
    echo Example: https://github.com/codeXpixel/studyplanner.git
    echo =======================================================
    echo.
    set /p repo_url="Paste the GitHub URL here and press ENTER: "
    goto :setup_remote
) else (
    echo Pushing existing code to GitHub...
    git push origin main
    if errorlevel 1 (
        echo Trying master branch instead...
        git push origin master
    )
    goto :end
)

:setup_remote
git branch -M main
set repo_url=%repo_url:"=%
git remote add origin "%repo_url%"
git push -u origin main
goto :end

:end
echo.
echo Finished! Check the messages above for any errors.
