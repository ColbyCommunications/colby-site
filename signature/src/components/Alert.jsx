const Alert = () => {
  return (
    <div
      className="alert"
      style={{
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        position: "fixed",
      }}
    >
      <div
        style={{
          padding: "0.5rem 0.75rem",
          display: "flex",
          alignItems: "center",
          backgroundColor: "rgb(34 197 94)",
          boxShadow:
            "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
        }}
      >
        <div
          style={{
            marginRight: "0.75rem",
            width: "1.5rem",
            height: "1.5rem",
            color: "rgb(34 197 94)",
            borderRadius: "9999px",
            backgroundColor: "white",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
          }}
        >
          <svg
            width="1.8em"
            height="1.8em"
            viewBox="0 0 16 16"
            className="bi bi-check"
            fill="currentColor"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              fillRule="evenodd"
              d="M10.97 4.97a.75.75 0 0 1 1.071 1.05l-3.992 4.99a.75.75 0 0 1-1.08.02L4.324 8.384a.75.75 0 1 1 1.06-1.06l2.094 2.093 3.473-4.425a.236.236 0 0 1 .02-.022z"
            />
          </svg>
        </div>
        <div style={{ color: "white", maxWidth: "20rem" }}>
          Signature copied!
        </div>
      </div>
    </div>
  );
};

export default Alert;
