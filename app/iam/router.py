"""Routes IAM — /auth/*, /me. HTTP uniquement : décode, appelle le service, encode."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import RedirectResponse

from app.core.errors import AppError
from app.core.ratelimit import rate_limit
from app.iam.dependencies import (
    AuthContext,
    get_auth_service,
    get_current_user,
    get_oauth_service,
)
from app.iam.oauth_service import OAuthService
from app.iam.schemas import (
    FounderProfileUpdateIn,
    LoginIn,
    MeOut,
    OAuthExchangeIn,
    OnboardingIn,
    RefreshIn,
    RegisterIn,
    TokenPair,
    UpdateMeIn,
    UserOut,
    VerifyEmailIn,
)
from app.iam.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenPair,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("auth_register", limit=5, window_seconds=60))],
)
async def register(
    body: RegisterIn,
    svc: AuthService = Depends(get_auth_service),
) -> TokenPair:
    return await svc.register(
        email=body.email, password=body.password, full_name=body.full_name, language=body.language
    )


@router.post(
    "/login",
    response_model=TokenPair,
    dependencies=[Depends(rate_limit("auth_login_ip", limit=10, window_seconds=60))],
)
async def login(
    body: LoginIn,
    svc: AuthService = Depends(get_auth_service),
) -> TokenPair:
    return await svc.login(email=body.email, password=body.password)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    body: RefreshIn,
    svc: AuthService = Depends(get_auth_service),
) -> TokenPair:
    return await svc.refresh(refresh_token=body.refresh_token)


# --- OAuth (Google, LinkedIn) — cf. OAuthService : design « code à usage unique » -------


@router.get("/oauth/{provider}/authorize")
async def oauth_authorize(
    provider: str,
    redirect_uri: str = Query(..., description="Callback FRONT où renvoyer le porteur."),
    svc: OAuthService = Depends(get_oauth_service),
) -> RedirectResponse:
    # Navigation navigateur : sur erreur on renvoie vers le login front (pas un JSON).
    try:
        url = await svc.build_authorize_redirect(provider, front_redirect_uri=redirect_uri)
    except AppError:
        return RedirectResponse(svc.public_login_error("oauth_provider"), status_code=307)
    return RedirectResponse(url, status_code=307)


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    svc: OAuthService = Depends(get_oauth_service),
) -> RedirectResponse:
    front_url = await svc.handle_callback(provider, code=code, state=state, error=error)
    return RedirectResponse(front_url, status_code=307)


@router.post(
    "/oauth/exchange",
    response_model=TokenPair,
    dependencies=[Depends(rate_limit("oauth_exchange", limit=10, window_seconds=60))],
)
async def oauth_exchange(
    body: OAuthExchangeIn,
    svc: OAuthService = Depends(get_oauth_service),
) -> TokenPair:
    # Le front échange le code à usage unique côté serveur → TokenPair (409 si conflit).
    return await svc.exchange(body.code)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshIn,
    svc: AuthService = Depends(get_auth_service),
) -> None:
    await svc.logout(refresh_token=body.refresh_token)


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
async def verify_email(
    body: VerifyEmailIn,
    svc: AuthService = Depends(get_auth_service),
) -> None:
    # Public : le token du lien EST l'authentification.
    await svc.verify_email(body.token)


@router.post(
    "/resend-verification",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("email_resend", limit=3, window_seconds=300))],
)
async def resend_verification(
    ctx: AuthContext = Depends(get_current_user),
    svc: AuthService = Depends(get_auth_service),
) -> None:
    await svc.resend_verification(ctx.user.id)


@router.get("/me", response_model=MeOut)
async def get_me(
    ctx: AuthContext = Depends(get_current_user),
    svc: AuthService = Depends(get_auth_service),
) -> MeOut:
    return await svc.me(ctx.user)


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UpdateMeIn,
    ctx: AuthContext = Depends(get_current_user),
    svc: AuthService = Depends(get_auth_service),
) -> UserOut:
    user = await svc.update_me(ctx.user, full_name=body.full_name, language=body.language)
    return UserOut.model_validate(user)


@router.patch("/me/profile", response_model=UserOut)
async def update_profile(
    body: FounderProfileUpdateIn,
    ctx: AuthContext = Depends(get_current_user),
    svc: AuthService = Depends(get_auth_service),
) -> UserOut:
    user = await svc.update_profile(ctx.user, body)
    return UserOut.model_validate(user)


@router.patch("/me/onboarding", response_model=UserOut)
async def complete_onboarding(
    body: OnboardingIn,
    ctx: AuthContext = Depends(get_current_user),
    svc: AuthService = Depends(get_auth_service),
) -> UserOut:
    user = await svc.complete_onboarding(
        ctx.user,
        country=body.country,
        city=body.city,
        professional_status=body.professional_status,
        project_stage=body.project_stage,
        weekly_availability=body.weekly_availability,
    )
    return UserOut.model_validate(user)
