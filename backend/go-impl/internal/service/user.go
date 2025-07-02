package service

import (
	"context"
	"errors"
	"strings"

	"LingChat/internal/data"
	"LingChat/internal/data/ent/ent"
	"LingChat/pkg/jwt"

	"github.com/google/uuid"
	"golang.org/x/crypto/bcrypt"
)

var (
	// ErrUserNotFound 用户不存在错误
	ErrUserNotFound = errors.New("用户不存在")
	// ErrInvalidPassword 密码错误
	ErrInvalidPassword = errors.New("密码错误")
	// ErrUserExists 用户已存在错误
	ErrUserExists = errors.New("用户已存在")
	// ErrEmailExists 邮箱已存在错误
	ErrEmailExists = errors.New("邮箱已存在")
	// ErrSamePassword 新密码与原密码相同错误
	ErrSamePassword = errors.New("新密码不能与原密码相同")
)

// UserService 用户服务接口
type UserService interface {
	// Register 注册用户
	Register(ctx context.Context, user *data.User) (*ent.User, string, error)
	// Login 登录
	Login(ctx context.Context, user *data.User) (*ent.User, string, error)
	// ChangePassword 修改密码
	ChangePassword(ctx context.Context, userID int64, oldPassword, newPassword string) error
}

type userService struct {
	ur  data.UserRepo
	jwt *jwt.JWT
}

// NewUserService 创建用户服务实例
func NewUserService(ur data.UserRepo, jwt *jwt.JWT) UserService {
	return &userService{
		ur:  ur,
		jwt: jwt,
	}
}

// Register 注册用户
func (s *userService) Register(ctx context.Context, user *data.User) (*ent.User, string, error) {
	if user == nil {
		return nil, "", errors.New("invalid register user data")
	}
	u, err := s.register(ctx, user.Username, user.Password, user.Email)
	if err != nil {
		return nil, "", err
	}
	token, err := s.jwt.GenerateToken(jwt.ClaimParams{
		UserID:   int(u.ID),
		Username: u.Username,
		Email:    u.Email,
		Role:     "user", // 默认角色
	}, 0)
	if err != nil {
		return nil, "", err
	}
	return u, token, nil
}

// Login 登录
func (s *userService) Login(ctx context.Context, user *data.User) (*ent.User, string, error) {
	if user == nil {
		return s.Register(ctx, &data.User{})
	}
	u, err := s.login(ctx, user.Username, user.Password)
	if err != nil {
		return nil, "", err
	}
	// 判断是否为root管理员账户
	role := "user"
	if u.Username == "root" {
		role = "admin"
	}

	token, err := s.jwt.GenerateToken(jwt.ClaimParams{
		UserID:   int(u.ID),
		Username: u.Username,
		Email:    u.Email,
		Role:     role,
	}, 0)
	if err != nil {
		return nil, "", err
	}
	return u, token, nil
}

// register 私有注册方法
func (s *userService) register(ctx context.Context, username, password, email string) (*ent.User, error) {
	// 如果所有参数都为空，则使用uuid创建用户名，密码置空
	if strings.TrimSpace(username) == "" && strings.TrimSpace(password) == "" && strings.TrimSpace(email) == "" {
		// 生成uuid并去掉连字符
		uuidStr := strings.ReplaceAll(uuid.New().String(), "-", "")
		// 使用uuid作为用户名
		username = uuidStr
		// 密码置空，不进行哈希
		password = ""
	} else {
		// 检查用户名是否已存在
		_, err := s.ur.GetByUsername(ctx, username)
		if err == nil {
			return nil, ErrUserExists
		}

		// 检查邮箱是否已存在
		if email != "" {
			_, err = s.ur.GetByEmail(ctx, email)
			if err == nil {
				return nil, ErrEmailExists
			}
		}

		// 加密密码
		hashedPassword, err := hashPassword(password)
		if err != nil {
			return nil, err
		}
		password = hashedPassword
	}

	// 创建用户
	user, err := s.ur.Create(ctx, &data.User{
		Username: username,
		Password: password,
		Email:    email,
	})
	if err != nil {
		return nil, err
	}

	return user, nil
}

// login 私有登录方法
func (s *userService) login(ctx context.Context, username, password string) (*ent.User, error) {
	// 通过用户名获取用户
	user, err := s.ur.GetByUsername(ctx, username)
	if err != nil {
		return nil, ErrUserNotFound
	}

	// 获取用户密码
	hashedPassword, err := s.ur.GetPassword(ctx, user.ID)
	if err != nil {
		return nil, err
	}

	if hashedPassword == "" {
		return user, nil
	}

	// 验证密码
	if err := verifyPassword(hashedPassword, password); err != nil {
		return nil, ErrInvalidPassword
	}

	return user, nil
}

// ChangePassword 修改密码
func (s *userService) ChangePassword(ctx context.Context, userID int64, oldPassword, newPassword string) error {
	// 验证用户是否存在
	_, err := s.ur.GetByID(ctx, userID)
	if err != nil {
		return ErrUserNotFound
	}

	// 获取用户当前密码哈希值
	hashedPassword, err := s.ur.GetPassword(ctx, userID)
	if err != nil {
		return err
	}

	// 验证原密码
	if err := verifyPassword(hashedPassword, oldPassword); err != nil {
		return ErrInvalidPassword
	}

	// 验证新密码不能与原密码相同
	if oldPassword == newPassword {
		return ErrSamePassword
	}

	// 对新密码进行哈希处理
	newHashedPassword, err := hashPassword(newPassword)
	if err != nil {
		return err
	}

	// 更新密码
	return s.ur.UpdatePassword(ctx, userID, newHashedPassword)
}

// hashPassword 加密密码
func hashPassword(password string) (string, error) {
	bytes, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	return string(bytes), err
}

// verifyPassword 验证密码
func verifyPassword(hashedPassword, password string) error {
	return bcrypt.CompareHashAndPassword([]byte(hashedPassword), []byte(password))
}
