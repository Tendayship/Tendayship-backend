# erd 구조

```
erDiagram
    %% 사용자 관련 테이블
    users {
        uuid user_id PK "사용자 고유 ID"
        string email UK "이메일 (카카오 로그인)"
        string name "이름"
        string phone "전화번호"
        date birth_date "생년월일"
        string profile_image_url "프로필 이미지 URL"
        timestamp created_at "가입일시"
        timestamp updated_at "수정일시"
    }
    
    %% 가족 그룹 관련
    family_groups {
        uuid group_id PK "그룹 고유 ID"
        string group_name "그룹명"
        uuid leader_id FK "리더 사용자 ID"
        string invite_code UK "초대 코드"
        enum deadline_type "마감일 타입(2주/4주)"
        enum status "상태(active/inactive)"
        timestamp created_at "생성일시"
        timestamp updated_at "수정일시"
    }
    
    %% 받는 분 정보
    recipients {
        uuid recipient_id PK "받는 분 고유 ID"
        uuid group_id FK "그룹 ID"
        string name "이름"
        date birth_date "생년월일"
        string phone "전화번호"
        string profile_image_url "프로필 이미지"
        string address "주소"
        string address_detail "상세주소"
        string postal_code "우편번호"
        timestamp created_at "생성일시"
        timestamp updated_at "수정일시"
    }
    
    %% 가족 구성원
    family_members {
        uuid member_id PK "멤버 고유 ID"
        uuid group_id FK "그룹 ID"
        uuid user_id FK "사용자 ID"
        uuid recipient_id FK "받는 분 ID"
        enum relationship "관계(딸/아들/며느리/사위 등)"
        enum role "역할(leader/member)"
        timestamp joined_at "가입일시"
    }
    
    %% 구독 정보
    subscriptions {
        uuid subscription_id PK "구독 고유 ID"
        uuid group_id FK "그룹 ID"
        uuid user_id FK "결제자 ID"
        enum status "상태(active/cancelled/expired)"
        date start_date "시작일"
        date end_date "종료일"
        date next_billing_date "다음 결제일"
        decimal amount "결제 금액"
        timestamp created_at "생성일시"
        timestamp updated_at "수정일시"
    }
    
    %% 결제 정보
    payments {
        uuid payment_id PK "결제 고유 ID"
        uuid subscription_id FK "구독 ID"
        string transaction_id "PG 거래 ID"
        decimal amount "결제 금액"
        enum status "상태(success/failed/pending)"
        string payment_method "결제 수단"
        timestamp paid_at "결제일시"
    }
    
    %% 회차 정보
    issues {
        uuid issue_id PK "회차 고유 ID"
        uuid group_id FK "그룹 ID"
        int issue_number "회차 번호"
        date deadline_date "마감일"
        enum status "상태(open/closed/published)"
        timestamp created_at "생성일시"
        timestamp closed_at "마감일시"
        timestamp published_at "발행일시"
    }
    
    %% 소식 게시글
    posts {
        uuid post_id PK "게시글 고유 ID"
        uuid issue_id FK "회차 ID"
        uuid author_id FK "작성자 ID"
        text content "내용(50-100자)"
        json image_urls "이미지 URL 배열"
        timestamp created_at "작성일시"
        timestamp updated_at "수정일시"
    }
    
    %% 책자 정보
    books {
        uuid book_id PK "책자 고유 ID"
        uuid issue_id FK "회차 ID"
        string pdf_url "PDF 파일 URL"
        enum production_status "제작상태(pending/completed)"
        enum delivery_status "배송상태(pending/shipping/delivered)"
        string tracking_number "운송장 번호"
        timestamp produced_at "제작일시"
        timestamp shipped_at "발송일시"
        timestamp delivered_at "배송완료일시"
    }
    
    %% 관계 정의
    users ||--o{ family_members : "has"
    family_groups ||--o{ family_members : "contains"
    family_groups ||--o| recipients : "has"
    family_groups ||--o{ issues : "has"
    family_groups ||--o| subscriptions : "has"
    
    users ||--o{ subscriptions : "pays"
    subscriptions ||--o{ payments : "has"
    
    recipients ||--o{ family_members : "related_to"
    
    issues ||--o{ posts : "contains"
    issues ||--o| books : "produces"
    
    users ||--o{ posts : "writes"
    users ||--o| family_groups : "leads"

```

# user flow

```
%%{init: {"flowchart": {"htmlLabels": false}} }%%
flowchart TB
    Start([시작]) --> Auth{로그인 상태?}

    Auth -->|비로그인| Login[카카오 로그인]:::authNode
    Auth -->|로그인됨| CheckGroup{가족 그룹 있음?}

    Login --> FirstTime{최초 가입?}
    FirstTime -->|Yes| ProfileSetup[프로필 등록]:::authNode
    FirstTime -->|No| CheckGroup
    ProfileSetup --> CheckGroup

    CheckGroup -->|없음| GroupChoice{"가족 만들기\n또는 초대받기?"}
    CheckGroup -->|있음| CheckSub{구독 활성?}

    %% 그룹 생성 플로우 (리더)
    GroupChoice -->|만들기| CreateGroup[가족 그룹 생성]:::groupNode
    CreateGroup --> SetDeadline["마감일 설정\n(2주/4주)"]:::groupNode
    SetDeadline --> Payment["결제 설정\n(월 6,900원)"]:::groupNode
    Payment --> RecipientInfo["받는 분 정보 입력"]:::groupNode
    RecipientInfo --> SetRelation[관계 설정]:::groupNode
    SetRelation --> GroupActive[그룹 활성화]

    %% 그룹 가입 플로우 (멤버)
    GroupChoice -->|초대받기| EnterCode[초대 코드 입력]:::groupNode
    EnterCode --> SelectRelation["받는 분과의 관계 선택"]:::groupNode
    SelectRelation --> GroupActive

    %% 구독 확인
    CheckSub -->|비활성| SubPrompt[구독 결제 안내]
    CheckSub -->|활성| MainHome[홈 피드]
    SubPrompt --> Payment
    GroupActive --> MainHome

    %% 메인 기능 플로우
    MainHome --> Action{사용자 행동}

    Action -->|소식 작성| WritePost["텍스트 작성\n(50-100자)"]:::actionNode
    WritePost --> AddImages["이미지 추가\n(최대 4장)"]:::actionNode
    AddImages --> SavePost[소식 저장]:::actionNode
    SavePost --> MainHome

    Action -->|소식함 보기| Library[소식함 목록]:::actionNode
    Library --> ViewBook["책자 열람/다운로드"]:::actionNode
    ViewBook --> MainHome

    Action -->|마이페이지| MyPage[내 정보 관리]:::actionNode
    MyPage --> MyAction{관리 항목}
    MyAction -->|프로필 수정| EditProfile[프로필 편집]:::actionNode
    MyAction -->|구독 관리| ManageSub["구독/결제 관리"]:::actionNode
    MyAction -->|가족 관리| ManageFamily["멤버 초대/관리"]:::actionNode
    MyAction -->|받는 분 수정| EditRecipient["받는 분 정보 수정"]:::actionNode

    EditProfile --> MainHome
    ManageSub --> MainHome
    ManageFamily --> MainHome
    EditRecipient --> MainHome

    %% 회차 마감 플로우
    MainHome --> DeadlineCheck{마감일 도래?}
    DeadlineCheck -->|D-7| Warning[마감 임박 알림]
    DeadlineCheck -->|D-Day| CloseIssue[회차 마감]
    Warning --> MainHome
    CloseIssue --> GenerateBook["책자 생성\n(어드민)"]:::adminNode
    GenerateBook --> UploadPDF["PDF 업로드"]:::adminNode
    UploadPDF --> UpdateStatus["배송 상태 업데이트"]:::adminNode
    UpdateStatus --> NewIssue[새 회차 시작]
    NewIssue --> MainHome

    %% 스타일 정의
    classDef authNode fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef groupNode fill:#f3e5f5,stroke:#4a148c,stroke-width:2px;
    classDef actionNode fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px;
    classDef adminNode fill:#fff3e0,stroke:#e65100,stroke-width:2px;
    
```