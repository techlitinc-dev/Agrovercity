# Tested API Endpoints

Swagger UI: http://localhost:8080/docs (OpenAPI: /openapi.json)

236 endpoints across 49 tags — all exercised by `backend/tests` (396 tests passing).

## addresses
- `DELETE /v1/addresses/{address_id}`
- `GET /v1/addresses`
- `POST /v1/addresses`
- `PUT /v1/addresses/{address_id}`

## admin
- `DELETE /v1/admin/content/{collection}/{doc_id}`
- `GET /v1/admin/analytics/summary`
- `GET /v1/admin/claims`
- `GET /v1/admin/kyc/pending`
- `GET /v1/admin/rates/pending`
- `GET /v1/admin/reports`
- `GET /v1/admin/settlements`
- `GET /v1/admin/users`
- `POST /v1/admin/broadcast`
- `POST /v1/admin/content/{collection}`
- `POST /v1/admin/kyc/{entity_id}/reject`
- `POST /v1/admin/kyc/{entity_id}/verify`
- `POST /v1/admin/login`
- `POST /v1/admin/rates/{rate_id}/approve`
- `POST /v1/admin/rates/{rate_id}/reject`
- `POST /v1/admin/reports/{report_id}/resolve`
- `POST /v1/admin/settlements/{settlement_id}/settle`
- `PUT /v1/admin/claims/{user_id}/{claim_id}`
- `PUT /v1/admin/content/{collection}/{doc_id}`
- `PUT /v1/admin/users/{user_id}/status`

## advisory
- `GET /v1/advisory/pest-radar`
- `POST /v1/advisory/disease-scan`
- `POST /v1/advisory/npk`
- `POST /v1/advisory/saturation`
- `POST /v1/advisory/sowing-intent`

## app-config
- `GET /v1/app-config`

## auth
- `POST /v1/auth/firebase-verify`
- `POST /v1/auth/mpin/reset`
- `POST /v1/auth/mpin/set`
- `POST /v1/auth/mpin/verify`
- `POST /v1/auth/refresh`
- `POST /v1/auth/register`

## bank-accounts
- `DELETE /v1/bank-accounts/{account_id}`
- `GET /v1/bank-accounts`
- `POST /v1/bank-accounts`
- `POST /v1/bank-accounts/{account_id}/set-primary`
- `POST /v1/bank-accounts/{account_id}/verify`

## chatbot
- `GET /v1/chatbot/history`
- `POST /v1/chatbot/handoff`
- `POST /v1/chatbot/messages`

## climate
- `GET /v1/climate/carbon-potential`
- `GET /v1/climate/resilient-varieties`

## content
- `GET /v1/channels`
- `GET /v1/channels/{channel_id}/chat`
- `GET /v1/news`
- `POST /v1/channels/{channel_id}/chat`

## contracts
- `GET /v1/contracts`
- `GET /v1/contracts/{contract_id}`
- `POST /v1/contracts/{contract_id}/accept`

## devices
- `DELETE /v1/devices/{token_hash}`
- `POST /v1/devices`

## diary
- `DELETE /v1/diary/entries/{entry_id}`
- `GET /v1/diary/entries`
- `GET /v1/diary/report`
- `POST /v1/diary/entries`

## equipment
- `DELETE /v1/equipment/bookings/{booking_id}`
- `GET /v1/equipment`
- `GET /v1/equipment/{equipment_id}/slots`
- `POST /v1/equipment/slots/{slot_id}/book`
- `POST /v1/equipment/slots/{slot_id}/waitlist`

## equipment-owner
- `GET /v1/equipment/bookings/pending`
- `GET /v1/equipment/owner/fleet`
- `POST /v1/equipment`
- `POST /v1/equipment/bookings/{booking_id}/approve`
- `POST /v1/equipment/bookings/{booking_id}/reject`
- `PUT /v1/equipment/{equipment_id}`

## finance
- `GET /v1/finance/credit-score`
- `GET /v1/finance/kcc`
- `GET /v1/finance/loans`
- `POST /v1/finance/loan-calculator`
- `POST /v1/finance/loans/apply`

## fpo
- `GET /v1/fpo/machinery`
- `GET /v1/fpo/me`
- `GET /v1/fpo/pools`
- `POST /v1/fpo/pools/{pool_id}/join`

## gamification
- `GET /v1/gamification/ledger`
- `GET /v1/gamification/rewards`
- `GET /v1/gamification/status`
- `POST /v1/gamification/redeem`

## gyan
- `GET /v1/blogs`
- `GET /v1/expert-talks`
- `GET /v1/videos`
- `GET /v1/workshops`
- `POST /v1/blogs/{blog_id}/bookmark`
- `POST /v1/blogs/{blog_id}/like`
- `POST /v1/expert-talks/{talk_id}/questions`
- `POST /v1/expert-talks/{talk_id}/register`
- `POST /v1/workshops/{workshop_id}/enroll`

## insurance
- `GET /v1/insurance/claims`
- `GET /v1/insurance/claims/{claim_id}`
- `GET /v1/insurance/policies`
- `GET /v1/insurance/policies/{policy_id}/certificate`
- `GET /v1/insurance/rates`
- `POST /v1/insurance/claims`
- `POST /v1/insurance/claims/{claim_id}/appeal`
- `POST /v1/insurance/policies/apply`

## jobs
- `POST /v1/jobs/rent-reminders/run`
- `POST /v1/jobs/settlements/run`

## land
- `DELETE /v1/land/leases/{lease_id}`
- `DELETE /v1/land/plots/{plot_id}`
- `GET /v1/land/leases`
- `GET /v1/land/leases/{lease_id}/payments`
- `GET /v1/land/plots`
- `POST /v1/land/leases`
- `POST /v1/land/leases/{lease_id}/payments`
- `POST /v1/land/plots`
- `PUT /v1/land/leases/{lease_id}`
- `PUT /v1/land/plots/{plot_id}`

## land-market
- `DELETE /v1/land/listings/{listing_id}`
- `GET /v1/land/lease-requests`
- `GET /v1/land/leases/{lease_id}/agreement-pdf`
- `GET /v1/land/listings`
- `GET /v1/land/listings/mine`
- `POST /v1/land/lease-requests`
- `POST /v1/land/lease-requests/{request_id}/accept`
- `POST /v1/land/lease-requests/{request_id}/reject`
- `POST /v1/land/listings`
- `PUT /v1/land/listings/{listing_id}`

## land-records
- `GET /v1/land-records/search`
- `GET /v1/land-records/{record_id}/pdf`
- `POST /v1/land-records/{record_id}/import`

## livestock
- `GET /v1/dairy-products`
- `GET /v1/gaushalas`
- `GET /v1/nurseries`
- `GET /v1/vets`
- `POST /v1/dairy-products/{product_id}/order`
- `POST /v1/gaushalas/{gaushala_id}/manure-order`
- `POST /v1/vets/bookings/{booking_id}/complete`
- `POST /v1/vets/{vet_id}/book`

## lots
- `DELETE /v1/market/lots/{lot_id}`
- `GET /v1/market/lots`
- `POST /v1/market/lots`
- `PUT /v1/market/lots/{lot_id}`

## mandi
- `GET /v1/mandi/compare`
- `GET /v1/mandi/list`
- `GET /v1/mandi/prices`
- `GET /v1/mandi/prices/history`
- `GET /v1/mandi/vyapari-rates`

## marketplace
- `DELETE /v1/cart/items/{product_id}`
- `GET /v1/cart`
- `GET /v1/products`
- `GET /v1/products/{product_id}`
- `GET /v1/products/{product_id}/certificate`
- `GET /v1/products/{product_id}/reviews`
- `POST /v1/cart/items`
- `POST /v1/products/{product_id}/reviews`
- `PUT /v1/cart/items/{product_id}`

## notifications
- `GET /v1/notifications`
- `POST /v1/notifications/read`

## orders
- `GET /v1/orders`
- `GET /v1/orders/{order_id}`
- `POST /v1/orders`
- `POST /v1/orders/{order_id}/cancel`
- `POST /v1/payments/razorpay/order`
- `POST /v1/payments/razorpay/refund`
- `POST /v1/payments/razorpay/verify`

## other
- `GET /v1/debug/sentry-test`
- `GET /v1/health`

## pnl
- `GET /v1/pnl/crops`
- `GET /v1/pnl/summary`
- `POST /v1/pnl/break-even`
- `POST /v1/pnl/crops/{crop_id}/expenses`

## post-harvest
- `GET /v1/post-harvest/cold-storage`
- `POST /v1/post-harvest/cold-storage/{facility_id}/book`
- `POST /v1/post-harvest/grade`

## ratings
- `GET /v1/ratings/providers/{provider_id}`
- `POST /v1/ratings`

## reference
- `GET /v1/geo/reverse`
- `GET /v1/languages`
- `GET /v1/regions/crops`

## referrals
- `GET /v1/referrals`
- `POST /v1/referrals/invite`

## schemes
- `GET /v1/schemes`
- `GET /v1/schemes/portals`
- `POST /v1/schemes/{scheme_id}/apply`

## seller
- `GET /v1/seller/rates/my`
- `POST /v1/seller/rates`

## settlements
- `GET /v1/broker/settlements`
- `GET /v1/equipment/settlements`
- `GET /v1/transport/settlements`

## soil-tests
- `GET /v1/soil-tests`
- `POST /v1/soil-tests/book`

## speech
- `POST /v1/speech/stt`
- `POST /v1/speech/tts`

## support
- `GET /v1/support/threads`
- `GET /v1/support/threads/{thread_id}/messages`
- `POST /v1/support/threads/{thread_id}/messages`

## sync
- `POST /v1/sync`

## transport
- `DELETE /v1/transport/vehicles/{vehicle_id}`
- `GET /v1/transport/bookings`
- `GET /v1/transport/vehicles`
- `GET /v1/transport/vehicles/my`
- `GET /v1/transport/vehicles/{vehicle_id}/calendar`
- `PATCH /v1/transport/bookings/{booking_id}`
- `POST /v1/transport/bookings`
- `POST /v1/transport/bookings/{booking_id}/accept`
- `POST /v1/transport/bookings/{booking_id}/reject`
- `POST /v1/transport/fare-estimate`
- `POST /v1/transport/vehicles`
- `PUT /v1/transport/vehicles/{vehicle_id}`
- `PUT /v1/transport/vehicles/{vehicle_id}/availability`

## tree
- `GET /v1/tree/articles`
- `GET /v1/tree/biofuel`
- `GET /v1/tree/care-guides`
- `GET /v1/tree/ngos`
- `POST /v1/tree/ngos/{ngo_id}/sapling-request`

## users
- `DELETE /v1/users/me`
- `DELETE /v1/users/me/blocks/{block_user_id}`
- `DELETE /v1/users/me/profiles/{profile_type}`
- `GET /v1/users/me`
- `GET /v1/users/me/blocks`
- `GET /v1/users/me/bookings`
- `GET /v1/users/me/consents`
- `POST /v1/users/me/blocks`
- `POST /v1/users/me/profiles`
- `POST /v1/users/me/profiles/{profile_type}/activate`
- `POST /v1/users/{user_id}/report`
- `PUT /v1/users/me`
- `PUT /v1/users/me/consents`
- `PUT /v1/users/me/farm-boundary`
- `PUT /v1/users/me/profiles/{profile_type}/primary`

## vault
- `DELETE /v1/vault/documents/{document_id}`
- `GET /v1/vault/documents`
- `POST /v1/vault/documents`

## water
- `GET /v1/water/canal-rotation`
- `GET /v1/water/groundwater`
- `GET /v1/water/schedule`
- `POST /v1/water/pmksy-calculator`

## weather
- `GET /v1/weather`

## women
- `GET /v1/women/home-enterprise`
- `GET /v1/women/shg`
- `POST /v1/women/shg/deposit`
