#pragma once

#include <string>

namespace SNPC
{
    namespace monads
    {

        template <typename T>
        class Error
        {
        public:
            constexpr bool ok() const noexcept
            {
                return m_is_valid;
            }

            constexpr const T &value() const noexcept
            {
                return m_value;
            }

            constexpr const T &value_or_throw() const
            {
                if (!m_is_valid)
                {
                    throw new std::exception();
                }
                return m_value;
            }

            constexpr T &mutable_value() const noexcept
            {
                return m_value;
            }

            constexpr T &mutable_value_or_throw() const
            {
                if (!m_is_valid)
                {
                    throw new std::exception();
                }
                return m_value;
            }

            constexpr const Error &with_error(std::string &&error) noexcept
            {
                m_error = std::move(error);
                return *this;
            }

            constexpr Error() noexcept : m_is_valid(false) {}

            constexpr Error(T &&x) noexcept :
                m_value(std::move(x)),
                m_is_valid(true) {}

            constexpr T &&release() noexcept
            {
                return m_value;
            }

            const std::string &error() const noexcept
            {
                return m_error;
            }

        private:
            const bool m_is_valid;
            std::string m_error;
            T m_value;
        };
    };
};